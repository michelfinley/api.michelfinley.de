import fastapi
import fastapi.security

import sqlalchemy.orm
from fastapi import Query

import schemas
import services

# Database setup script:
"""
import os

if os.path.exists("database.db"):
    os.remove("database.db")
services.create_database()

services.import_comicvine_data(next(services.get_db()))
"""

app = fastapi.FastAPI()


@app.get("/")
async def root_redirect():
    response = fastapi.responses.RedirectResponse("/docs")
    return response


@app.get("/api", response_model=dict[str, str])
async def hello_world():
    return {"message": "Hello World"}


# -------------------------------------------------------------------------------------------------------------------- #


@app.post("/api/users", response_model=dict[str, str])
async def create_user(
        user: schemas.UserCreate,
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    if len(user.password_hash) < 6:
        raise fastapi.HTTPException(status_code=400, detail="Password must contain at least six characters")

    if "@" in user.username:
        raise fastapi.HTTPException(status_code=400, detail="Username must not contain @")

    db_user = await services.get_user_by_email_or_username(user.email, db)
    if db_user:
        raise fastapi.HTTPException(status_code=409, detail="E-Mail already in use")

    db_user = await services.get_user_by_email_or_username(user.username, db)
    if db_user:
        raise fastapi.HTTPException(status_code=409, detail="Username already in use")

    user = await services.create_user(user, db)

    return await services.create_token(user)


@app.get("/api/users/me", response_model=schemas.User)
async def get_user(
        user: schemas.User = fastapi.Depends(services.get_current_user)
):
    return user


@app.put("/api/users/me", response_model=dict[str, str])
async def update_user(
        updated_user: schemas.UserUpdate,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.update_user(user.id, updated_user, db)


@app.delete("/api/users/me", response_model=dict[str, str])
async def delete_user(
        updated_user: schemas.UserUpdate,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.delete_user(user.id, updated_user, db)


@app.post("/api/token", response_model=dict[str, str])
async def generate_token(
        form_data: fastapi.security.OAuth2PasswordRequestForm = fastapi.Depends(),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    user = await services.authenticate_user(form_data.username, form_data.password, db)

    if user is None:
        raise fastapi.HTTPException(status_code=401, detail="Invalid Credentials")

    return await services.create_token(user)


# -------------------------------------------------------------------------------------------------------------------- #


@app.get("/api/posts/random", response_model=list[schemas.Post],
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_random_posts(
        count: int = 5,

        user: schemas.User = fastapi.Depends(services.get_current_user),

        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db),

        by_tag: int | None = Query(default=None),
        by_bot: int | None = Query(default=None),
        by_or_mentioned: int | None = Query(default=None),

        favorites_only: bool | None = Query(default=None),

        use_filter: str | None = Query(default=None),
        x: list[int] | None = Query(default=None),
):
    if x is None:
        x = []

    return await services.get_random_posts(
        count, user, db,
        by_tag=by_tag, by_bot=by_bot, by_or_mentioned=by_or_mentioned,
        favorites_only=favorites_only,
        use_filter=use_filter,
        exclude=x
    )


@app.get("/api/posts/random/info", response_model=schemas.FavoriteCount)
async def get_favorite_posts_count(
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_favorite_posts_count(user, db)


@app.get("/api/posts/{post_id}", response_model=schemas.Post,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_post(
        post_id: int,
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_post(post_id, db)


@app.get("/api/posts/{post_id}/info", response_model=schemas.PostInfo,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_post_info(
        post_id: int,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_post_info(post_id, db, user=user)


@app.post("/api/posts/{post_id}/favorite", response_model=schemas.PostInfo)
async def favorite_post(
        post_id: int,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.favorite_post(post_id, user, db)


@app.post("/api/posts/{post_id}/unfavorite", response_model=schemas.PostInfo)
async def unfavorite_post(
        post_id: int,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.unfavorite_post(post_id, user, db)


# -------------------------------------------------------------------------------------------------------------------- #


@app.get("/api/bots/random", response_model=list[schemas.Bot],
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_random_bots(
        count: int = 5,

        user: schemas.User = fastapi.Depends(services.get_current_user),

        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db),

        following_only: bool | None = Query(default=None),

        x: list[int] | None = Query(default=None),
):
    return await services.get_random_bots(count, user, db, following_only=following_only, exclude=x)


@app.get("/api/bots/random/info", response_model=schemas.FollowingCount)
async def get_followed_bot_count(
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_followed_bot_count(user, db)


@app.get("/api/bots/{bot_id_or_username}", response_model=schemas.Bot,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_bot(
        bot_id_or_username: int | str,
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_bot(bot_id_or_username, db)


@app.get("/api/bots/{bot_id_or_username}/info", response_model=schemas.BotInfo,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_bot_info(
        bot_id_or_username: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_bot_info(bot_id_or_username, db, user=user)


@app.post("/api/bots/{bot_id_or_username}/follow", response_model=schemas.BotInfo)
async def follow_bot(
        bot_id_or_username: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.follow_bot(bot_id_or_username, user, db)


@app.post("/api/bots/{bot_id_or_username}/unfollow", response_model=schemas.BotInfo)
async def unfollow_bot(
        bot_id_or_username: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.unfollow_bot(bot_id_or_username, user, db)


# -------------------------------------------------------------------------------------------------------------------- #


@app.get("/api/tags/random", response_model=list[schemas.Tag],
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_random_tags(
        count: int = 5,

        user: schemas.User = fastapi.Depends(services.get_current_user),

        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db),

        following_only: bool | None = Query(default=None),

        x: list[int] | None = Query(default=None),
):
    if x is None:
        x = []
    return await services.get_random_tags(count, user, db, following_only=following_only, exclude=x)


@app.get("/api/tags/random/info", response_model=schemas.FollowingCount)
async def get_followed_tag_count(
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_followed_tag_count(user, db)


@app.get("/api/tags/{tag_id_or_name}", response_model=schemas.Tag,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_tag(
        tag_id_or_name: int | str,
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_tag(tag_id_or_name, db)


@app.get("/api/tags/{tag_id_or_name}/info", response_model=schemas.TagInfo,
         dependencies=[fastapi.Depends(services.require_authentication)])
async def get_tag_info(
        tag_id_or_name: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.get_tag_info(tag_id_or_name, db, user=user)


@app.post("/api/tags/{tag_id_or_name}/follow", response_model=schemas.TagInfo)
async def follow_tag(
        tag_id_or_name: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.follow_tag(tag_id_or_name, user, db)


@app.post("/api/tags/{tag_id_or_name}/unfollow", response_model=schemas.TagInfo)
async def unfollow_tag(
        tag_id_or_name: int | str,
        user: schemas.User = fastapi.Depends(services.get_current_user),
        db: sqlalchemy.orm.Session = fastapi.Depends(services.get_db)
):
    return await services.unfollow_tag(tag_id_or_name, user, db)
