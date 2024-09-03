import pdfplumber
import pymupdf
import boto3
import os,io,json,urllib.parse,csv

#use pdfplumber to extract text and table
#use pymupdf to extract images

s3_client = boto3.client('s3')

#function to determine what content are NOT within the bounding boxes of the tables, to be used to filter out the table content in the text output
def not_within_bboxes(obj, bboxes):
    def obj_in_bbox(_bbox):
        """See https://github.com/jsvine/pdfplumber/blob/stable/pdfplumber/table.py#L404"""
        v_mid = (obj["top"] + obj["bottom"]) / 2
        h_mid = (obj["x0"] + obj["x1"]) / 2
        x0, top, x1, bottom = _bbox
        return (h_mid >= x0) and (h_mid < x1) and (v_mid >= top) and (v_mid < bottom)
    return not any(obj_in_bbox(__bbox) for __bbox in bboxes)

#depends on the format and layout of the pdf, pdfplumber may misidentify other elements such as image caption as tables
def is_valid_table(table):
    extracted = table.extract()
    return len(extracted) >= 2 and len(extracted[0]) >= 2

#to exclude "tables" misidentified by pdfplumber & record the location (coordinates) of the table extracted 
def extract_valid_tables(page, page_number):
    tables = page.find_tables()
    valid_tables = []
    table_locations = []
    for i, table in enumerate(tables):
        if is_valid_table(table):
            table_label = f"table_page_{page_number}_{i+1}"
            valid_tables.append((table_label, table.extract()))
            table_locations.append((f"<{table_label}>", table.bbox))
    return valid_tables, table_locations

#extract images and record the image location
def extract_images(pdf_document):
    images = []
    for page_index in range(len(pdf_document)):
        page = pdf_document[page_index]
        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            img_rect = page.get_image_rects(xref)[0]
            coords = (img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1)
            image_label = f"image_page_{page_index + 1}_{img_index + 1}"
            images.append((image_label, base_image, coords))
    return images

def lambda_handler(event, context):
    destination_bucket = os.environ['DESTINATION_BUCKET']

    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])

    pdf_name = os.path.splitext(os.path.basename(key))[0]

    tmp_file = '/tmp/input.pdf'
    s3_client.download_file(bucket, key, tmp_file)

    table_store = []
    element_locations = []

    # Extract images using PyMuPDF
    pdf_document = pymupdf.open(tmp_file)
    extracted_images = extract_images(pdf_document)
    pdf_document.close()

    with pdfplumber.open(tmp_file) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            valid_tables, table_locations = extract_valid_tables(page, page_number)
            
            table_store.extend(valid_tables)
            elements = table_locations.copy()

            # Add image elements for this page
            for img_label, _, coords in extracted_images:
                if img_label.startswith(f"image_page_{page_number}_"):
                    elements.append((f"<{img_label}>", coords))
            
            # Get bounding boxes of tables
            bboxes = [location[1] for location in table_locations]
            
            # Extract words and their positions, filtering out those within table bboxes
            words = page.extract_words(keep_blank_chars=False)
            filtered_words = [word for word in words if not_within_bboxes(word, bboxes)]
            
            # Combine all elements (tables, images, filtered words)
            all_elements = elements + [(word['text'], (word['x0'], word['top'], word['x1'], word['bottom'])) for word in filtered_words]
            
            # Sort all elements by their vertical position (top coordinate)
            all_elements.sort(key=lambda x: x[1][1])
            
            element_locations.append(all_elements)
    
    # Output text as txt with table labels
    txt_key = f'{pdf_name}/text/{pdf_name}.txt'
    text_content = ""
    for page_number, page_elements in enumerate(element_locations, start=1):
        text_content += f"--- Page {page_number} ---\n"
        for element,_ in page_elements:
            if element.startswith("<") and element.endswith(">"): #we label image and table with <>
                text_content += f"{element}\n"
            else:
                text_content += f"{element} "
        text_content += "\n\n"         
    
    s3_client.put_object(Bucket=destination_bucket, Key=txt_key, Body=text_content)

    # Output the tables as csv
    csv_keys = []
    for table_label, table_data in table_store:
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerows(table_data)  # This writes all rows, including the header
        csv_content = csv_buffer.getvalue()
        
        csv_key = f'{pdf_name}/tables/{table_label}.csv'
        s3_client.put_object(Bucket=destination_bucket, Key=csv_key, Body=csv_content)
        csv_keys.append(csv_key)

    # Upload extracted images to S3
    image_keys = []
    for img_label, img_data, _ in extracted_images:
        image_key = f'{pdf_name}/images/{img_label}.{img_data["ext"]}'
        s3_client.put_object(Bucket=destination_bucket, Key=image_key, Body=img_data["image"])
        image_keys.append(image_key)

    # Clean up
    os.remove(tmp_file)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'PDF parsed successfully',
            'pdf_name': pdf_name,
            'txt_file': txt_key,
            'csv_files': csv_keys,
            'image_files': image_keys
        })
    }