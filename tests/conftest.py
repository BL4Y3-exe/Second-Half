import os

# Tests always run on the scripted mock model, even when a .env file points at Foundry.
os.environ["FOUNDRY_PROJECT_ENDPOINT"] = ""
os.environ["FOUNDRY_MODEL"] = ""
