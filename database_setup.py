import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine
from passlib.apps import custom_app_context as pwd_context
import random
import string

Base = declarative_base()
secret_key = ''.join(random.choice(
    string.ascii_uppercase + string.digits) for x in xrange(32))


class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250))
    picture = Column(String(250))

class Ingredient(Base):
    __tablename__ = 'ingredient'
    id = Column(Integer, primary_key=True)
    amount = Column(String(50))
    description = Column(String(80))
    menu_id = Column(Integer, ForeignKey('menu.id'))

    @property
    def serialize(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'description': self.description,
        }


class Direction(Base):
    __tablename__ = 'direction'
    id = Column(Integer, primary_key=True)
    direction = Column(String(350))
    menu_id = Column(Integer, ForeignKey('menu.id'))

    @property
    def serialize(self):

        return {
            'id': self.id,
            'direction': self.direction,
        }


class WeeklyPlan(Base):
    __tablename__ = 'weekly_plan'
    id = Column(Integer, primary_key=True)
    menu_id = Column(Integer, ForeignKey('menu.id'))
    date = Column(String(10))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)


class Menu(Base):
    __tablename__ = 'menu'
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    picture = Column(String(250))
    servings = Column(Integer)
    calories = Column(Integer)
    hour = Column(Integer)
    minute = Column(Integer)
    category_id = Column(Integer, ForeignKey('category.id', ondelete='CASCADE'))
    # category = relationship(Category, backref=backref('children', passive_deletes=True))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    ingredients = relationship(Ingredient, cascade="save-update, merge, delete")
    directions = relationship(Direction, cascade="save-update, merge, delete")
    weeklyplan = relationship(WeeklyPlan, cascade="save-update, merge, delete")


    @property
    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'picture': self.picture,
            'servings': self.servings,
            'calories': self.calories,
            'hour': self.hour,
            'minute': self.minute,
            'category_id': self.category_id,
            'user_id': self.user_id
        }


class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)
    menu = relationship(Menu, cascade="save-update, merge, delete")


    @property
    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name
        }


engine = create_engine('sqlite:///recipes.db')
Base.metadata.create_all(engine)
