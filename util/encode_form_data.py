"""Tool to encode form data"""

def encode(data: dict) -> str:
    """
    Encode a dict of form data as a string

    Parameters:
        data: data about the new clearanace assignment

    Returns: the string of encoded data
    """
    def get_form_entries(data: dict, prefix: str = "") -> list[str]:
        """
        Convert the data dict into a list of form entries

        Parameters:
            data: data about the new clearance assignment

        Returns: list of strings representing key/value pairs
        """
        entries = []
        for key, val in data.items():
            if isinstance(val, (int, str)):
                if prefix:
                    entries.append(f"{prefix}[{key}]={val}")
                else:
                    entries.append(f"{key}={val}")
            elif isinstance(val, list):
                for i, list_item in enumerate(val):
                    if isinstance(list_item, dict):
                        entries.extend(get_form_entries(
                            data=list_item,
                            prefix=prefix + f"{key}[{i}]"
                        ))
                    elif prefix:
                        entries.append(f"{prefix}[{key}][]={list_item}")
                    else:
                        entries.append(f"{key}[]={list_item}")
        return entries

    return "&".join(get_form_entries(data))
