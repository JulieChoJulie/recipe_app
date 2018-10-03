from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, abort
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, User, Category, Menu, Ingredient, Direction

from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
import os

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///recipes.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

@app.route('/')
@app.route('/recipes/')
def recipeList():
    categories = session.query(Category).order_by(asc(Category.name))
    for category in categories:
        list = category.name.split()
        if list[0][0].isdigit():
            del list[0]
            category.name = " ".join(list)
            session.add(category)
            session.commit()
    if 'username' not in login_session:
        return render_template('publicRecipes.html', categories=categories)
    else:
        return render_template('recipes.html', categories=categories)

@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state, client_id=CLIENT_ID)

@app.route('/gconnect', methods=['POST'])
def gconnect():

    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state token'), 401)
        response.headers['Content-type'] = 'application/json'
        return response
    code = request.data
    try:
        # Upgrade the authorization code into a credentials object using
        # one-time-code.
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-type'] = 'application/json'
        return response
    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1'
           '/tokeninfo?access_token=%s' % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error'), 500))
        response.headers['Content-type'] = 'application/json'
        return response
    # Verify the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(json.dumps("Token's client ID does not match given user ID"), 401)
        response.headers['Content-type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401
        )
        print ("Token's client ID does not match app's.")
        response.headers['Content-type'] = 'application/json'
        return response

    # Check to see if user is already logged in
    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'), 200)
        response.headers['Content-type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    #Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt':'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if user_id is None:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' "style = "width: 300px; height: 300px; border-radius: ' \
              '150px;-webkit-border-radius: 150px;-moz-border-radius:150px;"'
    flash("You are now logged in as %s " % login_session['username'])
    return output

@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(json.dumps('Current user not connected'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Execute HTTP GET request to revoke current token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]

    if result['status'] == '200':
        # Reset the user's session.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['picture']
        del login_session['email']

        response = make_response(json.dumps('User successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # when the given token is invalid.
        response = make_response(json.dumps('Failed to revoke token for given user'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/recipes/new/', methods=['GET', 'POST'])
def newRecipe():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        valid = session.query(Category).filter_by(name = request.form['name']).one_or_none()
        if valid is None:
            newCat = Category(name = request.form['name'], user_id = login_session['user_id'])
            session.add(newCat)
            session.commit()
            return redirect(url_for('recipeList'))
        else:
            abort(400, description="The category name you entered is already being used.")

    else:
        return render_template('newRecipe.html')

@app.route('/recipes/<int:category_id>/')
def menuList(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    items = session.query(Menu).filter_by(category_id=category_id).all()
    creator = getUserInfo(category.user_id)
    print creator.id
    print login_session.get('user_id')
    list = category.name.split()
    if list[0][0].isdigit():
        del list[0]
        category.name = " ".join(list)
        session.add(category)
        session.commit()
    if login_session.get('user_id') == creator.id:
        return render_template('menu.html', category=category, category_id=category_id, items=items)
    elif 'username' in login_session:
        return render_template('userMenu.html', category=category, category_id=category_id, items=items)
    else:
        return render_template('publicMenu.html', category=category,category_id=category_id, items=items)

@app.route('/recipes/<int:category_id>/new/', methods=['GET', 'POST'])
def newMenu(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        valid = session.query(Menu).filter_by(name=request.form['name']).one_or_none()
        if valid is None:
            menu = Menu(user_id = login_session['user_id'], name=request.form['name'], picture=request.form['picture'], servings=request.form['servings'], calories=request.form['calories'], hour=request.form['hour'], minute=request.form['minute'], category_id=category_id)
            session.add(menu)
            session.commit()
            addedmenu = session.query(Menu).filter_by(name=request.form['name']).one()
            direction = Direction(menu_id=addedmenu.id, direction=request.form['direction'])
            session.add(direction)
            session.commit()
            ingredient = Ingredient(menu_id=addedmenu.id, amount=request.form['amount'], description=request.form['description'])
            session.add(ingredient)
            session.commit()
            return redirect(url_for('menuList', category_id=category.id))
        else:
            abort(400, description="The menu name you entered is already being used.")
    else:
        return render_template('newMenu.html', category=category)

@app.route('/recipes/<int:category_id>/edit/', methods=['GET', 'POST'])
def editRecipe(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if category.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to edit this category.');}</script><body onload='myFunction()'>"

    if request.method == 'POST':
        category.name = request.form['name']
        session.add(category)
        session.commit()
        return redirect(url_for('recipeList'))
    else:
        return render_template('editRecipe.html', category=category)

@app.route('/recipes/<int:category_id>/delete/', methods=['GET', 'POST'])
def deleteRecipe(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if category.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to delete this category.');}</script><body onload='myFunction()'>"

    if request.method == 'POST':
        session.delete(category)
        session.commit()
        return redirect(url_for('recipeList'))
    else:
        return render_template('deleteRecipe.html', category=category)

@app.route('/recipes/<int:category_id>/<int:menu_id>/')
def menuDetails(category_id, menu_id):
    item = session.query(Menu).filter_by(id=menu_id).one()
    ingredients = session.query(Ingredient).filter_by(menu_id=item.id).first()
    directions = session.query(Direction).filter_by(menu_id=item.id).first()
    creator = getUserInfo(item.user_id)

    if directions is not None:
        directions = session.query(Direction).filter_by(menu_id=item.id).all()
    else:
        directions = []
    if ingredients is not None:
        ingredients = session.query(Ingredient).filter_by(menu_id=item.id).all()
    else:
        ingredients = []

    if creator.id == login_session.get('user_id'):
        print "here"
        return render_template('menuDetails.html', category_id=category_id, item=item, ingredients=ingredients, directions=directions)
    else:
        return render_template('publicMenuDetails.html', category_id=category_id, item=item, ingredients=ingredients, directions=directions)


@app.route('/recipes/<int:category_id>/<int:menu_id>/edit', methods=['GET', 'POST'])
def editMenu(category_id, menu_id):
    category = session.query(Category).filter_by(id=category_id).one()
    item = session.query(Menu).filter_by(id=menu_id).one()
    ingredients = session.query(Ingredient).filter_by(menu_id=item.id).first()
    directions = session.query(Direction).filter_by(menu_id=item.id).first()
    if item.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to edit this menu.');}</script><body onload='myFunction()'>"

    if directions is not None:
        directions = session.query(Direction).filter_by(menu_id=item.id).all()
    else:
        directions = []
    if ingredients is not None:
        ingredients = session.query(Ingredient).filter_by(menu_id=item.id).all()
    else:
        ingredients = []
    if request.method == 'POST':
        # age = request.form.get('age', type=int)
        item.name = request.form['name']
        item.picture= request.form['picture']
        item.servings= request.form['servings']
        item.calories= request.form['calories']
        item.hour= int(request.form['hour'])
        item.minute=int(request.form['minute'])
        session.add(item)
        session.commit()

        amount = request.form.getlist('amount')
        descriptions = request.form.getlist('description')

        for i in range(0,len(descriptions)):
            description = descriptions[i]
            amt = amount[i]
            amt = amt.encode("utf-8")
            description = description.encode("utf-8")
            if len(description) == 0 and len(amount[i]) != 0:
                abort(400, description="You only entered the amount of ingredient: description is missing.")
            elif len(description) ==0:
                del amount[i]
                del descriptions[i]
            else:
                ingredient = Ingredient(amount=amt, description=description, menu_id=menu_id)
                session.add(ingredient)
                session.commit()

        directions = request.form.getlist('direction')

        for i in range(0, len(directions)):
            direc = directions[i]
            direc = direc.encode("utf-8")
            if len(direc) == 0:
                del directions[i]
            else:
                direction = Direction(menu_id=menu_id, direction=direc)
                session.add(direction)
                session.commit()

        ingredients = session.query(Ingredient).filter_by(menu_id=menu_id).all()
        directions = session.query(Direction).filter_by(menu_id=menu_id).all()
        return redirect(url_for('menuDetails', category_id=category.id, menu_id=menu_id, ingredients=ingredients, directions=directions))
    else:
        return render_template('editMenu.html', ingredients=ingredients, category=category, item=item, directions=directions)

@app.route('/recipes/<int:category_id>/<int:menu_id>/delete', methods=['GET', 'POST'])
def deleteMenu(category_id, menu_id):
    ingredients = session.query(Ingredient).filter_by(menu_id=menu_id).all()
    directions = session.query(Direction).filter_by(menu_id=menu_id).all()
    menu = session.query(Menu).filter_by(id=menu_id).one_or_none()
    category = session.query(Category).filter_by(id=category_id).one()
    if menu.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {alert('You are not authorized to delete this menu.');}</script><body onload='myFunction()'>"

    if request.method == 'POST':
        session.delete(menu)
        session.commit()
        for ingredient in ingredients:
            session.delete(ingredient)
            session.commit()
        for direction in directions:
            session.delete(direction)
            session.commit()
        return redirect(url_for('menuList', category_id=category.id))

    else:
        return render_template('deleteMenu.html', category=category, item=menu)

def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session['email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

if __name__ == '__main__':
    app.secret_key = os.urandom(24)
    app.debug = True
    app.run(host = '0.0.0.0', port = 5000)