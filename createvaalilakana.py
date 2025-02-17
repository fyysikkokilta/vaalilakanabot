import re
import json
import os
import requests

API_KEY = os.environ["API_KEY"]
API_USERNAME = os.environ["API_USERNAME"]

VAALILAKANA_POST_URL = os.environ["VAALILAKANA_POST_URL"]


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
                r"""^(?P<title>[^\/(]+?)"""
                r"""(?:\s*\/\s*(?P<title_en>[^(\d]+?))?"""
                r"""(?:\s*\((?P<amount>[^\)]+)\))?"""
                r"""(?:\s*(?P<application_dl>\d{1,2}\.\d{1,2}\.))?\s*$""",
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


def create_vaalilakana():
    headers = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
    }

    response = requests.get(
        VAALILAKANA_POST_URL,
        headers=headers,
        timeout=30,
    )

    body = response.json()
    vaalilakana_html = body["cooked"]

    # Remove applicants
    # Applicant lines are marked with a <li> tag
    text = re.sub(r"<li>.*?</li>", "", vaalilakana_html)

    # Remove HTML tags using regex
    text = re.sub(r"<.*?>", "", text)

    # Replace multiple newlines with a single newline
    text = re.sub(r"\n+", "\n", text).strip()

    # Ensure proper spacing and formatting
    text = text.replace("—", "").strip()

    return format_election_sheet(text)
