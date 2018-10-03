from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Base, User, Category, Menu, Ingredient, Direction
import json
engine = create_engine('sqlite:///recipes.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()

# path = 'C:\\Documents\\Username\\Path\\To\\File'
path = './crawler/crawler/spiders'

with open('{}/recipes-data.json'.format(path), 'r') as f:
    data=f.read()
    jsondata=json.loads(data)


# Add Fake User
User1 = User(name="Julie Cho", email="h32cho@gmail.com",
             picture='https://pbs.twimg.com/profile_images/2671170543/18debd694829ed78203a5a36dd364160_400x400.png')
session.add(User1)
session.commit()

for obj in jsondata:
    if session.query(Category).filter_by(name=obj['category']).one_or_none() is None:
        cat1 = Category(name=obj['category'], user_id=User1.id)
        session.add(cat1)
        session.commit()
    cat1= session.query(Category).filter_by(name=obj['category']).one()
    if session.query(Menu).filter_by(name=obj['name']).one_or_none() is None:
        menu1 = Menu(name=obj['name'], category_id=cat1.id, picture=obj['picture'], servings=obj['servings'], calories=obj['cal/serv'], user_id=cat1.user_id, hour=obj['time']['hour'], minute=obj['time']['minute'])
        session.add(menu1)
        session.commit()
        menu1 = session.query(Menu).filter_by(name=obj['name']).one()
        for ingre in obj['ingredients']:
            ingredient = Ingredient(amount=ingre['amount'], description=ingre['description'], menu_id=menu1.id)

            session.add(ingredient)
            session.commit()
        for direction in obj['directions']:
            direct = Direction(direction=direction, menu_id=menu1.id)
            session.add(direct)
            session.commit()
