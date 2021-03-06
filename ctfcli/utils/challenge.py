from pathlib import Path
from os.path import join

import yaml

import click

from .config import generate_session


class Yaml(dict):
    def __init__(self, data, file_path=None):
        super().__init__(data)
        self.file_path = Path(file_path)
        self.directory = self.file_path.parent


def load_challenge(path):
    try:
        with open(path) as f:
            return Yaml(data=yaml.safe_load(f.read()), file_path=path)
    except FileNotFoundError:
        click.secho(f"No challenge.yml was found in {path}", fg="red")
        return


def get_challenge(id):
    s = generate_session()
    return s.get(f"/api/v1/challenges/{id}", json=True).json()["data"]


def get_challenge_flags(id):
    s = generate_session()
    return s.get(f"/api/v1/challenges/{id}/flags", json=True).json()["data"]


def get_challenge_hints(id):
    s = generate_session()
    return s.get(f"/api/v1/challenges/{id}/hints", json=True).json()["data"]


def load_installed_challenges():
    s = generate_session()
    return s.get("/api/v1/challenges?view=admin", json=True).json()["data"]


def sync_challenge(challenge):
    data = {
        "name": challenge["name"],
        "category": challenge["category"],
        "description": challenge["description"],
        "type": challenge.get("type", "standard"),
        "value": int(challenge["value"]),
    }
    if challenge.get("attempts"):
        data["max_attempts"] = challenge.get("attempts")

    data["state"] = "hidden"

    installed_challenges = load_installed_challenges()
    for c in installed_challenges:
        if c["name"] == challenge["name"]:
            challenge_id = c["id"]
            break
    else:
        return

    s = generate_session()

    original_challenge = s.get(f"/api/v1/challenges/{challenge_id}", json=data).json()[
        "data"
    ]

    r = s.patch(f"/api/v1/challenges/{challenge_id}", json=data)
    r.raise_for_status()

    # Delete existing flags
    current_flags = s.get(f"/api/v1/flags", json=data).json()["data"]
    for flag in current_flags:
        if flag["challenge_id"] == challenge_id:
            flag_id = flag["id"]
            r = s.delete(f"/api/v1/flags/{flag_id}", json=True)
            r.raise_for_status()

    # Create new flags
    if challenge.get("flags"):
        for flag in challenge["flags"]:
            if type(flag) == str:
                data = {"content": flag, "type": "static", "challenge": challenge_id}
                r = s.post(f"/api/v1/flags", json=data)
                r.raise_for_status()
            elif type(flag) == dict:
                flag["challenge"] = challenge_id
                r = s.post(f"/api/v1/flags", json=flag)
                r.raise_for_status()

    # Delete existing tags
    current_tags = s.get(f"/api/v1/tags", json=data).json()["data"]
    for tag in current_tags:
        if tag["challenge_id"] == challenge_id:
            tag_id = tag["id"]
            r = s.delete(f"/api/v1/tags/{tag_id}", json=True)
            r.raise_for_status()

    # Update tags
    if challenge.get("tags"):
        for tag in challenge["tags"]:
            r = s.post(f"/api/v1/tags", json={"challenge": challenge_id, "value": tag})
            r.raise_for_status()

    # Delete existing files
    all_current_files = s.get(f"/api/v1/files?type=challenge", json=data).json()["data"]
    for f in all_current_files:
        for used_file in original_challenge["files"]:
            if f["location"] in used_file:
                file_id = f["id"]
                r = s.delete(f"/api/v1/files/{file_id}", json=True)
                r.raise_for_status()

    # Upload files
    if challenge.get("files"):
        files = []
        for f in challenge["files"]:
            file_path = Path(challenge.directory, f)
            if file_path.exists():
                file_object = ("file", file_path.open(mode="rb"))
                files.append(file_object)
            else:
                click.secho(f"File {file_path} was not found", fg="red")
                raise Exception(f"File {file_path} was not found")

        data = {"challenge": challenge_id, "type": "challenge"}
        # Specifically use data= here instead of json= to send multipart/form-data
        r = s.post(f"/api/v1/files", files=files, data=data)
        r.raise_for_status()

    # Delete existing hints
    current_hints = s.get(f"/api/v1/hints", json=data).json()["data"]
    for hint in current_hints:
        if hint["challenge_id"] == challenge_id:
            hint_id = hint["id"]
            r = s.delete(f"/api/v1/hints/{hint_id}", json=True)
            r.raise_for_status()

    # Create hints
    if challenge.get("hints"):
        for hint in challenge["hints"]:
            if type(hint) == str:
                data = {"content": hint, "cost": 0, "challenge": challenge_id}
            else:
                data = {
                    "content": hint["content"],
                    "cost": hint["cost"],
                    "challenge": challenge_id,
                }

            r = s.post(f"/api/v1/hints", json=data)
            r.raise_for_status()

    # Update requirements
    if challenge.get("requirements"):
        installed_challenges = load_installed_challenges()
        required_challenges = []
        for r in challenge["requirements"]:
            if type(r) == str:
                for c in installed_challenges:
                    if c["name"] == r:
                        required_challenges.append(c["id"])
            elif type(r) == int:
                required_challenges.append(r)

        required_challenges = list(set(required_challenges))
        data = {"requirements": {"prerequisites": required_challenges}}
        r = s.patch(f"/api/v1/challenges/{challenge_id}", json=data)
        r.raise_for_status()

    # Unhide challenge depending upon the value of "state" in spec
    data = {"state": "visible"}
    if challenge.get("state"):
        if challenge["state"] in ["hidden", "visible"]:
            data["state"] = challenge["state"]

    r = s.patch(f"/api/v1/challenges/{challenge_id}", json=data)
    r.raise_for_status()


def create_challenge(challenge):
    data = {
        "name": challenge["name"],
        "category": challenge["category"],
        "description": challenge["description"],
        "type": challenge.get("type", "standard"),
        "value": int(challenge["value"]),
    }
    if challenge.get("attempts"):
        data["max_attempts"] = challenge.get("attempts")

    s = generate_session()

    r = s.post("/api/v1/challenges", json=data)
    r.raise_for_status()

    challenge_data = r.json()
    challenge_id = challenge_data["data"]["id"]

    # Create flags
    if challenge.get("flags"):
        for flag in challenge["flags"]:
            if type(flag) == str:
                data = {"content": flag, "type": "static", "challenge": challenge_id}
                r = s.post(f"/api/v1/flags", json=data)
                r.raise_for_status()
            elif type(flag) == dict:
                flag["challenge"] = challenge_id
                r = s.post(f"/api/v1/flags", json=flag)
                r.raise_for_status()

    # Create tags
    if challenge.get("tags"):
        for tag in challenge["tags"]:
            r = s.post(f"/api/v1/tags", json={"challenge": challenge_id, "value": tag})
            r.raise_for_status()

    # Upload files
    if challenge.get("files"):
        files = []
        for f in challenge["files"]:
            file_path = Path(challenge.directory, f)
            if file_path.exists():
                file_object = ("file", file_path.open(mode="rb"))
                files.append(file_object)
            else:
                click.secho(f"File {file_path} was not found", fg="red")
                raise Exception(f"File {file_path} was not found")

        data = {"challenge": challenge_id, "type": "challenge"}
        # Specifically use data= here instead of json= to send multipart/form-data
        r = s.post(f"/api/v1/files", files=files, data=data)
        r.raise_for_status()

    # Add hints
    if challenge.get("hints"):
        for hint in challenge["hints"]:
            if type(hint) == str:
                data = {"content": hint, "cost": 0, "challenge": challenge_id}
            else:
                data = {
                    "content": hint["content"],
                    "cost": hint["cost"],
                    "challenge": challenge_id,
                }

            r = s.post(f"/api/v1/hints", json=data)
            r.raise_for_status()

    # Add requirements
    if challenge.get("requirements"):
        installed_challenges = load_installed_challenges()
        required_challenges = []
        for r in challenge["requirements"]:
            if type(r) == str:
                for c in installed_challenges:
                    if c["name"] == r:
                        required_challenges.append(c["id"])
            elif type(r) == int:
                required_challenges.append(r)

        required_challenges = list(set(required_challenges))
        data = {"requirements": {"prerequisites": required_challenges}}
        r = s.patch(f"/api/v1/challenges/{challenge_id}", json=data)
        r.raise_for_status()

    # Set challenge state
    if challenge.get("state"):
        data = {"state": "hidden"}
        if challenge["state"] in ["hidden", "visible"]:
            data["state"] = challenge["state"]

        r = s.patch(f"/api/v1/challenges/{challenge_id}", json=data)
        r.raise_for_status()


def lint_challenge(path):
    try:
        challenge = load_challenge(path)
    except yaml.YAMLError as e:
        click.secho(f"Error parsing challenge.yml: {e}", fg="red")
        exit(1)

    required_fields = ["name", "author", "category", "description", "value"]
    errors = []
    for field in required_fields:
        if challenge.get(field) is None:
            errors.append(field)

    if len(errors) > 0:
        print("Missing fields: ", ", ".join(errors))
        exit(1)

    exit(0)


def dump_challenge(challenge, challenge_folder_path):
    # Retrieve the challenge informations
    challenge = get_challenge(challenge["id"])

    data = {
        "name": challenge["name"],
        "category": challenge["category"],
        "description": challenge["description"],
        "type": challenge["type"],
        "value": int(challenge["value"]),
        "attempts": int(challenge["attempts"]),
        "state": challenge["state"],
    }

    if challenge.get("tags"):
        data["tags"] = challenge.get("tags")

    # Retrieve the flags of the challenge
    flags = get_challenge_flags(challenge["id"])

    if flags:
        flags_data = []

        for flag in flags:
            flag_data = {
                "type": flag["type"],
                "content": flag["content"],
            }

            if flag["data"]:
                flag_data["data"] = flag["data"]

            flags_data.append(flag_data)

        data["flags"] = flags_data

    # Retrieve the hints of the challenge
    hints = get_challenge_hints(challenge["id"])

    if hints:
        hints_data = []

        for hint in hints:
            if hint["cost"] != 0:
                hint_data = {"content": hint["content"], "cost": int(hint["cost"])}
            else:
                hint_data = hint["content"]

            hints_data.append(hint_data)

        data["hints"] = hints_data

    # Save the challenge information in 'challenge.yml' in the folder of the challenge
    with open(join(challenge_folder_path, "challenge.yml"), "w") as challenge_file:
        yaml.dump(data, challenge_file)

    click.secho(f"{challenge['name']} successfully dumped !", fg="green")
