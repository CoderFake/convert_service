

def remove_bom(header_name):
    try:
        header = header_name.lstrip('\ufeff')
        header = header.replace("\ufeff", "")
    except Exception as e:
        return header_name
    return header