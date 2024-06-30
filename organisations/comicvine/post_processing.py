# Da nicht alle Posts über diesen Algorithmus fehlerfrei in die Datenbank übertragen werden können,
#  da Llama in der Formatierung des Outputs immer variiert,
#  habe ich die Datenbank nach dem Ausführen dieses Skripts noch einmal per Hand berichtigt.

import os

from organisations.comicvine import models, database


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Für die finale Datenbank wurden Posts aus beiden Ordnern, von 14:21 und 15:24 Uhr verwendet.
directory = os.path.join("posts_test", "2024-06-17@15-24")  # , "2024-06-17@14-21")

filepaths = os.listdir(directory)

final_posts = []  # list[ tuple[ character, post ] ]

for filepath in filepaths:
    character_name = filepath.split("_")[-1][:-4]

    with open(os.path.join(directory, filepath), encoding="utf-8") as file:
        raw_posts = file.read()

    raw_posts_split = raw_posts.split("\n")
    posts = []
    match len(raw_posts_split):

        case 2:
            print("Geppetto...")

        case 5:
            for post in raw_posts_split:
                if "\"  \"" in post:
                    post_split = post[1:-1].split("\"  \"")
                    for i in post_split:
                        posts.append(i)
                else:
                    posts.append(post[1:-1])

        case 6:
            for post in raw_posts_split[1:]:
                posts.append(post[3:].replace("\"", ""))

        case 8:
            for post in raw_posts_split[1:]:
                if len(post) > 1:
                    if post[0].isdigit():
                        posts.append(post[4:-1])

        case 9:
            for post in raw_posts_split[1:]:
                if len(post) != 25:
                    posts.append(post)

        case 10:
            for post in raw_posts_split[1:]:
                if not post.startswith("Tweet "):
                    if post.startswith("\""):
                        posts.append(post[1:-1])
                    else:
                        posts.append(post)

        case 11:
            for post in raw_posts_split[1:]:
                if not post.startswith("Tweet "):
                    if post.startswith("\""):
                        posts.append(post[1:-1])

        case 12:
            for post in raw_posts_split[1:]:
                if not post.startswith("Tweet "):
                    if post.startswith("\""):
                        posts.append(post[1:-1])

        case 13:
            for post in raw_posts_split[1:]:
                if len(post) > 1:
                    if post[0].isdigit():
                        posts.append(post[3:])

        case 14:
            for post in raw_posts_split[1:]:
                if not post.startswith("Tweet "):
                    if len(post) > 1:
                        posts.append(post)

        case 15:
            for post in raw_posts_split[2:]:
                if not post.startswith("Tweet "):
                    if len(post) > 1:
                        posts.append(post)

        case 18:
            for post in raw_posts_split[1:]:
                if not post.startswith("Tweet "):
                    if len(post) > 1:
                        posts.append(post[1:-1])

        case 19:
            for post in raw_posts_split[1:]:
                if post.startswith("\""):
                    posts.append(post.replace("\"", ""))

        case 24:
            for post in raw_posts_split[1:]:
                if post.startswith("\""):
                    posts.append(post.replace("\"", ""))

        case _:
            print(character_name)
            raise Exception

    for i in posts:
        final_posts.append((character_name, i))

comicvine_db = next(get_db())

for character, post in final_posts:
    print(character, "|", post, "\n")
    character_id = comicvine_db.query(models.Character).filter_by(username=character).first().id
    post = models.Post(
        content=post,
        owner_id=character_id
    )
    comicvine_db.add(post)
    comicvine_db.commit()
    comicvine_db.refresh(post)
