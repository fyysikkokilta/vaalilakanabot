import re
import json
import os


def format_election_sheet(text):
    divisions = {}
    lines = text.strip().split("\n")

    current_division_name = None

    for line in lines:
        # Check for division headers (sections marked with uppercase and a slash)
        match_division = re.match(r"^([A-ZÄÖÜ\- ]+) / ([A-ZÄÖÜa-z\- ]+)$", line)
        if match_division:
            current_division_name = match_division.group(1).strip()
            divisions[current_division_name] = {
                "division": current_division_name,
                "division_en": match_division.group(2).strip(),
                "roles": {},
            }
            continue

        # Check for roles (ignore if no active division exists)
        if current_division_name:
            match_role = re.match(
                r"^(?P<title>[^\/(]+?)(?:\s*\/\s*(?P<title_en>[^(\d]+?))?(?:\s*\((?P<amount>[^\)]+)\))?(?:\s*(?P<application_dl>\d{1,2}\.\d{1,2}\.))?\s*$",
                line,
            )
            if match_role:
                title = match_role.group(1).strip()
                title_en = (
                    match_role.group(2).strip() if match_role.group(2) else title
                )  # Default to title
                amount = match_role.group(3).strip() if match_role.group(3) else None
                application_dl = (
                    match_role.group(4).strip() if match_role.group(4) else None
                )

                divisions[current_division_name]["roles"][title] = {
                    "title": title,
                    "title_en": title_en,  # If no translation, set to Finnish title
                    "amount": amount,
                    "application_dl": application_dl,
                    "applicants": [],
                }

    # Ensure directory exists before writing the file
    os.makedirs("data", exist_ok=True)

    # Write to file
    with open("data/vaalilakana.json", "w+", encoding="utf-8") as f:
        json.dump(divisions, f, indent=2, ensure_ascii=False)

    return divisions
