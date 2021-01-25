import os

from ctfcli.utils.challenge import load_installed_challenges, dump_challenge


class Dump(object):
    def challenges(self):
        challenges = load_installed_challenges()

        for challenge in challenges:
            name = challenge["name"]
            category = challenge["category"]

            challenge_path = os.path.join(category, name)

            if not os.path.isdir(challenge_path):
                # Create the challenge folder
                os.makedirs(challenge_path, exist_ok=True)

                # Dump the challenge in the challenge and create a 'challenge.yml' file with the challenge informations
                dump_challenge(challenge, challenge_path)
