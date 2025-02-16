from datetime import datetime
import json
import os
import requests

API_KEY = os.environ["API_KEY"]
API_USERNAME = os.environ["API_USERNAME"]

VAALILAKANA_POST_URL = os.environ["VAALILAKANA_POST_URL"]

# Election positions
BOARD = os.environ["BOARD"].split(",")
ELECTED_OFFICIALS = os.environ["ELECTED_OFFICIALS"].split(",")
OTHER_ELECTED = os.environ["OTHER_ELECTED"].split(",")

YEAR = datetime.now().year


def json_to_markdown(json_data):
    # Parse the JSON data
    data = json.loads(json_data)

    # Start building the HTML
    text = f"# VAALILAKANA {YEAR} / ELECTION SHEET {YEAR}\n\n"

    # Iterate over each division
    for division_data in data.values():
        division_name = division_data["division"]
        division_name_en = division_data["division_en"]

        # Add division header
        text += f"### {division_name} / {division_name_en}\n\n"

        # Iterate over each role in the division
        for role_key, role_data in division_data["roles"].items():
            role_title = role_data["title"]
            role_title_en = role_data["title_en"]
            role_amount = role_data["amount"]
            role_application_dl = role_data["application_dl"]
            role_applicants = role_data["applicants"]

            # Determine if the role is a board role or official role
            if role_key in BOARD:
                role_tag = "**"
            elif role_key in ELECTED_OFFICIALS + OTHER_ELECTED:
                role_tag = "*"
            else:
                role_tag = None

            role_row = ""
            if role_tag:
                role_row += role_tag
            role_row += role_title
            if role_title_en != role_title:
                role_row += f" / {role_title_en}"
            if role_amount:
                role_row += f" ({role_amount})"
            if role_application_dl:
                role_row += f" {role_application_dl}"
            if role_tag:
                role_row += role_tag
            role_row += "\n"
            text += role_row

            # Add applicants list
            if len(role_applicants) > 0:
                text += "\n"
                for applicant in role_applicants:
                    applicant_name = applicant["name"]
                    if applicant["valittu"]:
                        text += f"* **{applicant_name}**\n"
                    else:
                        text += f"* {applicant_name}\n"
                text += "\n"

            text += "\n"

        text += "—\n\n"

    return text


def update_election_sheet(context):
    # Read the JSON data
    with open("data/vaalilakana.json", "r", encoding="utf-8") as f:
        json_data = f.read()

    # Convert JSON to HTML
    text = json_to_markdown(json_data)

    headers = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
        "Content-Type": "application/json",
    }

    payload = {
        "raw": text,
    }

    return requests.put(
        VAALILAKANA_POST_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )
