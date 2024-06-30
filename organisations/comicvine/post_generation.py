import datetime
import os
import random

from ctransformers import AutoModelForCausalLM

from organisations.comicvine import database, models


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database():
    return database.Base.metadata.create_all(bind=database.engine)


def create_prompt_v2(character: models.Character, character_list: list[str]) -> str:
    return_string = (f"{character.nickname + ', alias ' if character.nickname else ''}"
                     f"{character.username} is a {character.gender} comic character.\n")
    return_string += f"{character.summary}\n"
    return_string += f"{character.username}'s powers include {character.powers}\n"
    return_string += (f"Using their outlined character traits to align the posts with their personality, "
                      f"generate a total of 5 Tweets which may be posted by {character.username}.\n")

    # Für Posts aus dem Ordner 2024-06-17@14-21 wurde folgender Code ergänzt,
    # um mehr Varianz zwischen den einzelnen Posts zu haben
    """return_string += f"Be encouraged to also mention or refer to the following comic characters:\n"
    return_string += ", ".join(character_list) + "\n"""
    return return_string


model = AutoModelForCausalLM.from_pretrained("TheBloke/Llama-2-13b-Chat-GGUF",
                                             model_file="llama-2-13b-chat.q5_K_M.gguf",
                                             model_type="llama", gpu_layers=50, context_length=1024)

start_datetime = datetime.datetime.now().strftime("%Y-%m-%d@%H-%M")

comicvine_db = next(get_db())

characters = [character.username for character in comicvine_db.query(models.Character).all()]

all_characters = characters.copy()

character_count = len(characters)

for i in range(character_count):
    current_character_name = random.choice(characters)
    characters.remove(current_character_name)
    current_character = comicvine_db.query(models.Character).filter_by(username=current_character_name).first()

    print(f"({i + 1} / {character_count}): {current_character.username}")

    other_character_names = all_characters.copy()
    other_character_names.remove(current_character_name)
    prompt = create_prompt_v2(current_character, other_character_names)
    print(f"\nCurrent prompt:\n\n{prompt}")

    response = model(prompt, max_new_tokens=1024)

    current_datetime = datetime.datetime.now().strftime("%Y-%m-%d@%H-%M-%S")

    print(f"Result @{current_datetime}:\n{response}\n\n")

    if not os.path.isdir("posts_test"):
        os.mkdir("posts_test")

    if not os.path.isdir(f"posts_test/{start_datetime}"):
        os.mkdir(f"posts_test/{start_datetime}")

    with open(f"posts_test/{start_datetime}/{current_datetime}_{current_character.username}.txt", "w+",
              encoding="utf-8") as file:
        file.write(response)

    print(f"\n{'-'*32}\n")
