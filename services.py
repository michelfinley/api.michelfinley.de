import random
import re
from collections.abc import Generator

import argon2
import fastapi
import fastapi.security
import jwt
from pydantic import ValidationError
from sqlalchemy import func, or_, and_, not_
import sqlalchemy.orm

import database
import models
import schemas

from organisations.comicvine import models as comicvine_models
from organisations.comicvine import database as comicvine_database


oauth2scheme = fastapi.security.OAuth2PasswordBearer(tokenUrl="/api/token")

with open("jwt_secret") as file:
    jwt_secret = file.read()

ph = argon2.PasswordHasher()


# <editor-fold desc="Database operations">
def create_database() -> None:
    return database.Base.metadata.create_all(bind=database.engine)


def get_db() -> Generator[sqlalchemy.orm.Session]:
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()
# </editor-fold>


# <editor-fold desc="User operations">
async def get_user_by_email_or_username(email_or_username: str, db: sqlalchemy.orm.Session) -> schemas.User | None:
    if "@" in email_or_username:
        user = db.query(models.User).filter_by(email=email_or_username).first()
    else:
        user = db.query(models.User).filter_by(username=email_or_username).first()
    if user is None:
        return
    return schemas.User.model_validate(user)


async def create_user(user: schemas.UserCreate, db: sqlalchemy.orm.Session) -> schemas.User:
    user_obj = models.User(email=user.email, password_hash=ph.hash(user.password_hash), username=user.username)
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)
    return user_obj


async def update_user(user_id: int, updated_user: schemas.UserUpdate, db: sqlalchemy.orm.Session) -> dict[str, str]:
    user = db.query(models.User).get(user_id)

    if not verify_password(user, updated_user.password_hash, db):
        raise fastapi.HTTPException(401, "Wrong password")

    if updated_user.username:
        if db.query(models.User).filter_by(username=updated_user.username).first() is not None:
            raise fastapi.HTTPException(409, "Username already in use")
        user.username = updated_user.username

    if updated_user.email:
        if db.query(models.User).filter_by(email=updated_user.email).first() is not None:
            raise fastapi.HTTPException(409, "Email already in use")
        user.email = updated_user.email

    if updated_user.new_password:
        user.password_hash = ph.hash(updated_user.new_password)

    db.commit()
    db.refresh(user)

    return {"message": "successfully updated user"}


async def delete_user(user_id: int, updated_user: schemas.UserUpdate, db: sqlalchemy.orm.Session) -> dict[str, str]:
    user = db.query(models.User).get(user_id)

    if not verify_password(user, updated_user.password_hash, db):
        raise fastapi.HTTPException(401, "Wrong password")

    follows = db.query(models.FollowingMap).filter_by(follower_id=user.id).all()

    for follow in follows:
        db.delete(follow)
        db.commit()

    favorites = db.query(models.FavoriteMap).filter_by(user_id=user.id).all()

    for favorite in favorites:
        db.delete(favorite)
        db.commit()

    db.delete(user)
    db.commit()

    return {"message": "successfully deleted user"}
# </editor-fold>


# <editor-fold desc="User authentication">
def verify_password(user: models.User, password: str, db: sqlalchemy.orm.Session) -> bool:
    try:
        if ph.verify(user.password_hash, password):
            if ph.check_needs_rehash(user.password_hash):
                print(f"Rehashed password of user with id {user.id}")
                user.password_hash = ph.hash(password)

                db.commit()
                db.refresh(user)
            return True
    except (argon2.exceptions.VerifyMismatchError, argon2.exceptions.InvalidHashError):
        return False
    except argon2.exceptions.VerificationError as error:
        print(error)
        return False


async def authenticate_user(email_or_username: str, password: str, db: sqlalchemy.orm.Session) -> models.User | None:
    user = await get_user_by_email_or_username(email_or_username, db)

    if user is None:
        return

    if not verify_password(user, password, db):
        return

    return user


async def create_token(user: models.User) -> dict[str, str]:
    user_obj = schemas.User.from_orm(user)

    payload = {"id": user_obj.id}

    token = jwt.encode(payload, jwt_secret)

    return dict(access_token=token, token_type="bearer")


def get_current_user(token: str = fastapi.Depends(oauth2scheme),
                     db: sqlalchemy.orm.Session = fastapi.Depends(get_db)) -> schemas.User:
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user = db.query(models.User).get(payload["id"])

        return schemas.User.model_validate(user)

    except (jwt.exceptions.DecodeError, ValidationError):
        raise fastapi.HTTPException(status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                                    detail="Could not validate credentials")


def require_authentication(token: str = fastapi.Depends(oauth2scheme),
                           db: sqlalchemy.orm.Session = fastapi.Depends(get_db)) -> bool | None:
    if get_current_user(token, db):
        return True
# </editor-fold>


# <editor-fold desc="User associated data">
async def get_favorite_posts_count(user: models.User, db: sqlalchemy.orm.Session) -> schemas.FavoriteCount:
    favorite_count = db.query(func.count(models.FavoriteMap.id)).filter_by(user_id=user.id).scalar()
    return schemas.FavoriteCount(
        id=user.id,

        favorite_count=favorite_count,
    )


async def get_followed_bot_count(user: models.User, db: sqlalchemy.orm.Session) -> schemas.FollowingCount:
    following_count = (db.query(func.count(models.FollowingMap.id)).
                       filter_by(follower_id=user.id).
                       filter(models.FollowingMap.bot_id != None).
                       scalar())
    return schemas.FollowingCount(
        id=user.id,

        following_count=following_count,
    )


async def get_followed_tag_count(user: models.User, db: sqlalchemy.orm.Session) -> schemas.FollowingCount:
    following_count = (db.query(func.count(models.FollowingMap.id)).
                       filter_by(follower_id=user.id).
                       filter(models.FollowingMap.tag_id != None).
                       scalar())
    return schemas.FollowingCount(
        id=user.id,

        following_count=following_count,
    )
# </editor-fold>


# <editor-fold desc="Posts">
async def get_post(post_id: int, db: sqlalchemy.orm.Session) -> schemas.Post:
    post = db.query(models.Post).get(post_id)

    if post is None:
        raise fastapi.HTTPException(status_code=404, detail=f"There is no post with id {post_id}")

    return schemas.Post.model_validate(post)


async def get_random_posts(
        count: int,

        user: models.User,

        db: sqlalchemy.orm.Session,

        by_tag: int = None,
        by_bot: int = None,
        by_or_mentioned: int = None,

        favorites_only: bool = None,

        use_filter: str = None,

        exclude: list[int] = None
) -> list[schemas.Post]:
    remaining_posts_count = db.query(func.count(models.Post.id))

    if by_tag:
        remaining_posts_count = remaining_posts_count.filter(models.Post.id.in_(
            [i.post_id for i in db.query(models.TagMap).filter(models.TagMap.tag_id.is_(by_tag)).all()]
        ))

    if by_bot:
        remaining_posts_count = remaining_posts_count.filter_by(owner_id=by_bot)

    if by_or_mentioned:
        remaining_posts_count = remaining_posts_count.filter(
            or_(models.Post.owner_id.is_(by_or_mentioned),
                (models.Post.id.in_([i.post_id for i in db.query(models.MentionMap).
                                     filter_by(mention_id=by_or_mentioned).all()])))
        )

    if favorites_only:
        remaining_posts_count = remaining_posts_count.filter(models.Post.id.in_(
            [i.post_id for i in db.query(models.FavoriteMap).filter_by(user_id=user.id).all()]
        ))

    if use_filter:
        remaining_posts_count = remaining_posts_count.filter(and_(
            models.Post.content.contains(i, autoescape=True) for i in use_filter.split(" ")
        ))

    remaining_posts_count = remaining_posts_count.scalar()

    posts = []

    if len(exclude) >= remaining_posts_count:
        return posts
    elif len(exclude) + count > remaining_posts_count:
        count = remaining_posts_count - len(exclude)

    for i in range(count):
        post_pos = random.randint(0, remaining_posts_count - len(exclude) - 1)

        post = db.query(models.Post).filter(models.Post.id.not_in(exclude))

        if by_tag:
            post = post.filter(models.Post.id.in_(
                [i.post_id for i in db.query(models.TagMap).filter(models.TagMap.tag_id.is_(by_tag)).all()]
            ))

        if by_bot:
            post = post.filter_by(owner_id=by_bot)

        if by_or_mentioned:
            post = post.filter(
                or_(models.Post.owner_id.is_(by_or_mentioned),
                    (models.Post.id.in_([i.post_id for i in db.query(models.MentionMap).
                                        filter_by(mention_id=by_or_mentioned).all()])))
            )

        if favorites_only:
            post = post.filter(models.Post.id.in_(
                [i.post_id for i in db.query(models.FavoriteMap).filter_by(user_id=user.id).all()]
            ))

        if use_filter:
            post = post.filter(and_(
                models.Post.content.contains(i, autoescape=True) for i in use_filter.split(" ")
            ))

        post = post.offset(post_pos).first()
        exclude.append(post.id)
        posts.append(schemas.Post.model_validate(post))

    return posts


async def get_post_info(post_id: int, db: sqlalchemy.orm.Session, user: models.User = None) -> schemas.PostInfo:
    post = await get_post(post_id, db)

    if user is None:
        favorite = None
    else:
        # noinspection PyComparisonWithNone
        favorite = (db.query(models.FavoriteMap).
                    filter_by(post_id=post.id).
                    filter_by(user_id=user.id).first() != None)

    post_info = schemas.PostInfo(
        id=post.id,

        favorite=favorite,

        favorite_count=db.query(func.count(models.FavoriteMap.id)).filter_by(post_id=post.id).scalar(),
    )

    return schemas.PostInfo.model_validate(post_info)
# </editor-fold>


# <editor-fold desc="Posts / favorite">
async def favorite_post(post_id: int, user: models.User, db: sqlalchemy.orm.Session) -> schemas.PostInfo:
    post = db.query(models.Post).get(post_id)

    if post is None:
        raise fastapi.HTTPException(status_code=404, detail=f"There is no post with id {post_id}")

    post = schemas.Post.model_validate(post)

    favorite = db.query(models.FavoriteMap).filter_by(user_id=user.id).filter_by(post_id=post.id).first()

    if favorite is not None:
        raise fastapi.HTTPException(status_code=404, detail=f"Post with id {post_id} already is in your favorites")

    favorite = models.FavoriteMap(post_id=post.id, user_id=user.id)

    db.add(favorite)
    db.commit()
    db.refresh(favorite)

    return await get_post_info(post_id, db, user=user)


async def unfavorite_post(post_id: int, user: models.User, db: sqlalchemy.orm.Session) -> schemas.PostInfo:
    post = db.query(models.Post).get(post_id)

    if post is None:
        raise fastapi.HTTPException(status_code=404, detail=f"There is no post with id {post_id}")

    post = schemas.Post.model_validate(post)

    favorite = db.query(models.FavoriteMap).filter_by(user_id=user.id).filter_by(post_id=post.id).first()

    if favorite is None:
        raise fastapi.HTTPException(status_code=404, detail=f"Post with id {post_id} is not in your favorites")

    db.delete(favorite)
    db.commit()

    return await get_post_info(post_id, db, user=user)
# </editor-fold>


# <editor-fold desc="Bots">
async def get_bot(bot_id_or_username: int | str, db: sqlalchemy.orm.Session) -> schemas.Bot:
    if bot_id_or_username.isdigit():
        bot = db.query(models.Bot).get(bot_id_or_username)

        if bot is None:
            raise fastapi.HTTPException(status_code=404,
                                        detail=f"Bot with ID {bot_id_or_username} does not exist")

    else:
        bot_id_or_username = bot_id_or_username.lstrip("@")

        bot = db.query(models.Bot).filter_by(username=bot_id_or_username).first()

        if bot is None:
            raise fastapi.HTTPException(status_code=404,
                                        detail=f"Bot with username {bot_id_or_username} does not exist")

    return schemas.Bot.model_validate(bot)


async def get_random_bots(count: int, user: models.User, db: sqlalchemy.orm.Session,
                          following_only: bool = None, exclude: list[int] = None) -> list[schemas.Bot]:
    if exclude is None:
        exclude = []

    remaining_bots_count = db.query(func.count(models.Bot.id))

    if following_only:
        remaining_bots_count = remaining_bots_count.filter(models.Bot.id.in_(
            [i.bot_id for i in db.query(models.FollowingMap).filter_by(follower_id=user.id).all()]
        ))

    remaining_bots_count = remaining_bots_count.scalar()

    bots = []

    if len(exclude) >= remaining_bots_count:
        return bots
    elif len(exclude) + count > remaining_bots_count:
        count = remaining_bots_count - len(exclude)

    for i in range(count):
        bot_pos = random.randint(0, remaining_bots_count - len(exclude) - 1)

        bot = db.query(models.Bot).filter(models.Bot.id.not_in(exclude))

        if following_only:
            bot = bot.filter(models.Bot.id.in_(
                [i.bot_id for i in db.query(models.FollowingMap).filter_by(follower_id=user.id).all()]
            ))

        bot = bot.offset(bot_pos).first()

        exclude.append(bot.id)
        bots.append(schemas.Bot.model_validate(bot))

    return bots


async def get_bot_info(bot_id_or_name: int | str,
                       db: sqlalchemy.orm.Session, user: models.User = None) -> schemas.BotInfo:
    bot = await get_bot(bot_id_or_name, db)

    if user is None:
        following = None
    else:
        # noinspection PyComparisonWithNone
        following = (db.query(models.FollowingMap).
                     filter_by(bot_id=bot.id).
                     filter_by(follower_id=user.id).first() != None)

    bot_info = schemas.BotInfo(
        id=bot.id,

        following=following,

        post_count=db.query(func.count(models.Post.id)).filter_by(owner_id=bot.id).scalar(),
        favorites_count=db.query(func.count(models.FavoriteMap.id)).filter(models.FavoriteMap.post_id.in_(
            [i.id for i in db.query(models.Post).filter_by(owner_id=bot.id).all()]
        )).scalar(),
        followers_count=db.query(func.count(models.FollowingMap.id)).filter_by(bot_id=bot.id).scalar(),
        mentioned_count=db.query(func.count(models.MentionMap.id)).filter_by(mention_id=bot.id).filter(
            not_(models.MentionMap.post_id.in_([i.id for i in db.query(models.Post).filter_by(owner_id=bot.id).all()]))
        ).scalar(),
    )

    return schemas.BotInfo.model_validate(bot_info)
# </editor-fold>


# <editor-fold desc="Bots / follow">
async def follow_bot(bot_id_or_name: int | str,
                     user: models.User, db: sqlalchemy.orm.Session) -> schemas.BotInfo:
    bot = await get_bot(bot_id_or_name, db)

    follow = db.query(models.FollowingMap).filter_by(bot_id=bot.id).filter_by(follower_id=user.id).first()

    if follow is not None:
        raise fastapi.HTTPException(status_code=409,
                                    detail=f"You are already following the bot "
                                           f"{'with the id ' if bot_id_or_name.isdigit() else ''}"
                                           f"{bot_id_or_name}")

    follow = models.FollowingMap(bot_id=bot.id, follower_id=user.id)

    db.add(follow)
    db.commit()
    db.refresh(follow)

    return await get_bot_info(bot_id_or_name, db, user=user)


async def unfollow_bot(bot_id_or_name: int | str,
                       user: models.User, db: sqlalchemy.orm.Session) -> schemas.BotInfo:
    bot = await get_bot(bot_id_or_name, db)

    follow = db.query(models.FollowingMap).filter_by(bot_id=bot.id).filter_by(follower_id=user.id).first()

    if follow is None:
        raise fastapi.HTTPException(status_code=409, detail=f"You are not following the bot "
                                                            f"{'with the id ' if bot_id_or_name.isdigit() else ''}"
                                                            f"{bot_id_or_name}")

    db.delete(follow)
    db.commit()

    return await get_bot_info(bot_id_or_name, db, user=user)
# </editor-fold>


# <editor-fold desc="Tags">
async def get_tag(tag_id_or_name: int | str, db: sqlalchemy.orm.Session) -> schemas.Tag:
    if tag_id_or_name.isdigit():
        tag = db.query(models.Tag).get(tag_id_or_name)

    else:
        tag_id_or_name = tag_id_or_name.lstrip("#")

        tag = db.query(models.Tag).filter_by(name=tag_id_or_name).first()

    if tag is None:
        raise fastapi.HTTPException(status_code=404, detail=f"Tag with name {tag_id_or_name} does not exist")

    return schemas.Tag.model_validate(tag)


async def get_random_tags(count: int, user: models.User, db: sqlalchemy.orm.Session,
                          following_only: bool = None, exclude: list[int] = None) -> list[schemas.Tag]:
    if exclude is None:
        exclude = []

    remaining_tags_count = db.query(func.count(models.Tag.id))

    if following_only:
        remaining_tags_count = remaining_tags_count.filter(models.Tag.id.in_(
            [i.tag_id for i in db.query(models.FollowingMap).filter_by(follower_id=user.id).all()]
        ))

    remaining_tags_count = remaining_tags_count.scalar()

    tags = []

    if len(exclude) >= remaining_tags_count:
        return tags
    elif len(exclude) + count > remaining_tags_count:
        count = remaining_tags_count - len(exclude)

    for i in range(count):
        tag_pos = random.randint(0, remaining_tags_count - len(exclude) - 1)

        tag = db.query(models.Tag).filter(models.Tag.id.not_in(exclude))

        if following_only:
            tag = tag.filter(models.Tag.id.in_(
                [i.tag_id for i in db.query(models.FollowingMap).filter_by(follower_id=user.id).all()]
            ))

        tag = tag.offset(tag_pos).first()

        exclude.append(tag.id)
        tags.append(schemas.Tag.model_validate(tag))

    return tags


async def get_tag_info(tag_id_or_name: int | str,
                       db: sqlalchemy.orm.Session, user: models.User = None) -> schemas.TagInfo:
    tag = await get_tag(tag_id_or_name, db)

    if user is None:
        following = None
    else:
        # noinspection PyComparisonWithNone
        following = (db.query(models.FollowingMap).
                     filter_by(tag_id=tag.id).
                     filter_by(follower_id=user.id).first() != None)

    tag_info = schemas.TagInfo(
        id=tag.id,

        following=following,

        post_count=db.query(func.count(models.TagMap.id)).filter_by(tag_id=tag.id).scalar(),
        follower_count=db.query(func.count(models.FollowingMap.id)).filter_by(tag_id=tag.id).scalar(),
    )

    return schemas.TagInfo.model_validate(tag_info)
# </editor-fold>


# <editor-fold desc="Tags / follow">
async def follow_tag(tag_id_or_name: int | str,
                     user: models.User, db: sqlalchemy.orm.Session) -> schemas.TagInfo:
    tag = await get_tag(tag_id_or_name, db)

    following_map = db.query(models.FollowingMap).filter_by(tag_id=tag.id).filter_by(follower_id=user.id).first()

    if following_map is not None:
        raise fastapi.HTTPException(status_code=409, detail=f"You are already following the tag "
                                                            f"{'with the id ' if tag_id_or_name.isdigit() else ''}"
                                                            f"{tag_id_or_name}")

    following_map = models.FollowingMap(tag_id=tag.id, follower_id=user.id)

    db.add(following_map)
    db.commit()
    db.refresh(following_map)

    return await get_tag_info(tag_id_or_name, db, user=user)


async def unfollow_tag(tag_id_or_name: int | str,
                       user: models.User, db: sqlalchemy.orm.Session) -> schemas.TagInfo:
    tag = await get_tag(tag_id_or_name, db)

    follow = db.query(models.FollowingMap).filter_by(tag_id=tag.id).filter_by(follower_id=user.id).first()

    if follow is None:
        raise fastapi.HTTPException(status_code=409, detail=f"You are not following the tag "
                                                            f"{'with the id ' if tag_id_or_name.isdigit() else ''}"
                                                            f"{tag_id_or_name}")

    db.delete(follow)
    db.commit()

    return await get_tag_info(tag_id_or_name, db, user=user)
# </editor-fold>


# <editor-fold desc="ComicVine Import">
def get_comicvine_db() -> Generator[sqlalchemy.orm.Session]:
    db = comicvine_database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def import_comicvine_data(db: sqlalchemy.orm.Session) -> None:
    comicvine_name = "ComicVine"

    comicvine_organisation = models.Organisation(
        name=comicvine_name
    )

    db.add(comicvine_organisation)
    db.commit()
    db.refresh(comicvine_organisation)

    comicvine_id = db.query(models.Organisation).filter_by(name=comicvine_name).first().id

    comicvine_db = next(get_comicvine_db())

    for i in range(1, comicvine_db.query(func.count(comicvine_models.Character.id)).scalar() + 1):
        character = comicvine_db.query(comicvine_models.Character).get(i)

        bot = models.Bot()
        bot.owner_id = comicvine_id
        bot.username = (str(character.username).lower().
                        replace(" ", "_").
                        replace(".", "").
                        replace("'", ""))
        bot.nickname = character.nickname if character.nickname else character.username
        bot.image = character.image
        bot.background_color = "bg-navy-800"

        db.add(bot)
        db.commit()
        db.refresh(bot)

    original_character_list = comicvine_db.query(comicvine_models.Character).all()

    for i in range(1, comicvine_db.query(func.count(comicvine_models.Post.id)).scalar(), 1):
        original_post = comicvine_db.query(comicvine_models.Post).get(i)

        if original_post is None:
            continue

        post = models.Post()

        owner = comicvine_db.query(comicvine_models.Character).get(original_post.owner_id)
        post.owner_id = db.query(models.Bot).filter_by(image=owner.image).first().id

        post.content = original_post.content

        db.add(post)
        db.commit()
        db.refresh(post)

        for p, bot in enumerate(original_character_list):
            post.content = re.sub(fr"\w*(?<![a-zA-Z#]){bot.username}",
                                  f"@{db.query(models.Bot).filter_by(image=bot.image).first().username}", post.content)

        for j in re.findall(r"\w*(?<![a-zA-Z])[@#]\w+", post.content):
            if j[0] == "#":
                tag = db.query(models.Tag).filter_by(name=j[1:].lower()).first()

                if tag is None:
                    tag = models.Tag(name=j[1:].lower())
                    db.add(tag)
                    db.commit()
                    db.refresh(tag)

                tag_map = models.TagMap(tag_id=tag.id, post_id=post.id)

                db.add(tag_map)
                db.commit()
                db.refresh(tag_map)

            else:
                bot: models.Bot | None = db.query(models.Bot).filter_by(username=j[1:]).first()

                if bot is None:
                    continue

                mention_map = models.MentionMap(post_id=post.id, mention_id=bot.id)

                db.add(mention_map)
                db.commit()
                db.refresh(mention_map)

            continue
    return
# </editor-fold>
