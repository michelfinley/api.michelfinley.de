import os

from simyan.comicvine import Comicvine
from simyan.sqlite_cache import SQLiteCache

from organisations.comicvine import database
from organisations.comicvine.models import Character


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_database():
    return database.Base.metadata.create_all(bind=database.engine)


if __name__ == '__main__':
    db_path = os.path.join(*os.path.split(os.path.abspath(__file__))[:-1], "comicvine_data.db")
    if os.path.isfile(db_path):
        print("Removing existing database...")
        os.remove(db_path)

    print("Creating database...")
    create_database()
    comicvine_db = next(get_db())

    print("Fetching data...")

    with open("api_key") as file:
        api_key = file.read()

    session = Comicvine(api_key=api_key, cache=SQLiteCache())

    character_ids = [
        22892,  # Tarzan
        36802,  # Jane Porter (Frau von Tarzan)
        35482,  # Korak, Tarzan's Sohn

        65186,  # Dracula
        62851,  # Abraham Van Helsing

        38840,  # Frankensteins Monster

        14335,  # Robin Hood

        63244,  # Sherlock Holmes
        27015,  # Dr. Watson

        9793,   # King Arthur
        39132,  # Merlin (aus King Arthur)
        6891,   # Morgan le Fay (aus King Arthur)
        21095,  # Sir Lancelot (aus King Arthur)

        39859,  # Geppetto (Pinocchio's "Vater")
        34473,  # Pinocchio

        37176,  # Schneewittchen
        36109,  # The Evil Queen (aus Schneewittchen)

        4581,   # Red Riding Hood
        21010,  # Big Bad Wolf

        21451,  # Alice
        21464,  # White Rabbit (Alice im Wunderland)
        21460,  # Cheshire Cat (Alice im Wunderland)

        21540,  # Captain Hook
        7868,   # Tinker Bell
        39853,  # Peter Pan

        34103,  # John Carter
        34145,  # Dejah Thoris (Princess of Mars, Wife of John Carter)

        15216,  # Cisco Kid

        9826,   # Cinderella

        65451,  # Aladdin

                # The Wizard of Oz
        24723,  # Dorothy Gale
        24728,  # Tin Woodman
        21478,  # Toto
        24726,  # Scarecrow
        24717,  # Cowardly Lion
        25373,  # Wicked Witch of the West
        16744,  # Glinda, Good Witch of the North

        57793,  # Baloo
        56982,  # Mowgli

        33979,  # Prince Charming

        39780,  # Humpty Dumpty

        7264,   # Little Boy Blue
    ]

    for pos, character_id in enumerate(character_ids):
        print(f"({pos + 1} / {len(character_ids)}) Character ID: {character_id}")

        result = session.get_character(character_id)

        character = Character()

        character.comicvine_id = result.id

        if result.real_name is not None and result.real_name != result.name:
            character.nickname = result.real_name

        character.username = result.name

        character.image = result.image.original_url

        character.summary = result.summary

        character.gender = ["", "Male", "Female", "Other"][result.gender]

        if result.date_of_birth is not None:
            character.date_of_birth = result.date_of_birth.strftime("%d %b %Y")

        character.powers = ", ".join([i.name for i in result.powers])

        comicvine_db.add(character)
        comicvine_db.commit()
        comicvine_db.refresh(character)

        print(f"Finished fetching character {character.comicvine_id} ({character.username})\n")
