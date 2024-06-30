import sqlalchemy as sql
import sqlalchemy.orm as orm

import database as database


class User(database.Base):
    __tablename__ = "users"

    id = sql.Column(sql.Integer, primary_key=True, index=True)

    email = sql.Column(sql.String, unique=True, index=True)
    password_hash = sql.Column(sql.String)

    username = sql.Column(sql.String, unique=True, index=True)


class Organisation(database.Base):
    __tablename__ = "organisations"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    name = sql.Column(sql.String, unique=True, index=True)

    bots = orm.relationship("Bot", back_populates="owner")


class Bot(database.Base):
    __tablename__ = "bots"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    owner_id = sql.Column(sql.Integer, sql.ForeignKey("organisations.id"))

    username = sql.Column(sql.String, unique=True, index=True)
    nickname = sql.Column(sql.String)

    image = sql.Column(sql.String)
    background_color = sql.Column(sql.String)

    posts = orm.relationship("Post", back_populates="owner")

    owner = orm.relationship("Organisation", back_populates="bots")


class Post(database.Base):
    __tablename__ = "posts"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    owner_id = sql.Column(sql.Integer, sql.ForeignKey("bots.id"))

    content = sql.Column(sql.String)

    owner = orm.relationship("Bot", back_populates="posts")


class Tag(database.Base):
    __tablename__ = "tags"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    name = sql.Column(sql.String, index=True)


class TagMap(database.Base):
    __tablename__ = "tagmap"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    post_id = sql.Column(sql.Integer, index=True)
    tag_id = sql.Column(sql.Integer, index=True)


class MentionMap(database.Base):
    __tablename__ = "mentionmap"
    id = sql.Column(sql.Integer, primary_key=True)
    post_id = sql.Column(sql.Integer, index=True)
    mention_id = sql.Column(sql.Integer, index=True)


class FavoriteMap(database.Base):
    __tablename__ = "favoritemap"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    user_id = sql.Column(sql.Integer, index=True)
    post_id = sql.Column(sql.Integer, index=True)


class FollowingMap(database.Base):
    __tablename__ = "followingmap"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    tag_id = sql.Column(sql.Integer, index=True)
    bot_id = sql.Column(sql.Integer, index=True)
    follower_id = sql.Column(sql.Integer, index=True)
