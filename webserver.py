from flask import (Flask,
                   app,
                   render_template,
                   request,
                   redirect,
                   jsonify,
                   url_for,
                   flash,
                   abort,
                   g)
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import (Base,
                            User,
                            Category,
                            Menu,
                            Ingredient,
                            Direction,
                            WeeklyPlan)

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
from functools import wraps


from datetime import timedelta

app = Flask(__name__)

# Store google client id
CLIENT_ID = json.loads(open('client_secrets.json', 'r')
                       .read())['web']['client_id']

engine = create_engine('sqlite:///recipes.db?check_same_thread=False')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Automatically logout login_session after 5 min
@app.before_request
def make_session_permanent():
    login_session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=5)

def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'username' in login_session:
            return f(*args, **kwargs)
        else:
            flash("You need to login first")
            return redirect(url_for('showLogin'))
    return wrap
# Homepage
@app.route('/')
@app.route('/recipes/')
def recipeList():
    categories = session.query(Category).order_by(asc(Category.name))
    menu = session.query(Menu).order_by(asc(Menu.name))
    pic = []
    for cat in categories:
        menuPic = session.query(Menu).filter_by(category_id=cat.id).first()
        if menuPic is None:
            pic.append("")
        else:
            pic.append(menuPic.picture)
    pic.reverse()

    res = []
    for category in categories:
        list = category.name.split()
        if list[0][0].isdigit():
            del list[0]
            category.name = " ".join(list)
            session.add(category)
            session.commit()
    print(login_session)
    if 'username' not in login_session:
        return render_template('publicRecipes.html',
                               categories=categories, pic=pic)
    else:
        dates = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        dates.reverse()
        plans = planner(login_session['user_id'])
        user = login_session
        for plan in plans:
            menu = session.query(Menu).filter_by(id=plan).one()
            res.append(menu)
        return render_template('recipes.html',
                               categories=categories, list=res,
                               dates=dates, pic=pic, user=user)

# Refresh weekly dinner plan and redirect to the homepage
@app.route('/recipes/refresh/')
def refresh():
    plans = session.query(WeeklyPlan)\
        .filter_by(user_id=login_session['user_id']).all()
    for plan in plans:
        session.delete(plan)
        session.commit()
    return redirect(url_for('recipeList'))


# JSON APIs to view Category Information
@app.route('/recipes/json/')
def recipeListJSON():
    categories = session.query(Category).all()
    return jsonify(CategoryList=[c.serialize for c in categories])

# Login page
@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state, client_id=CLIENT_ID)

# Get customized & stored weekly planner for the logged in user.
def planner(user_id):
    user = session.query(User).filter_by(id=user_id).one
    plan = session.query(WeeklyPlan).filter_by(user_id=user_id).first()

    if plan is None:
        main = []
        side = []
        categories = session.query(Category).order_by(asc(Category.name))

        for category in categories:
            if 'Dinner' in category.name or 'Dish' in category.name:
                menus = session.query(Menu)\
                    .filter_by(category_id=category.id).all()
                for menu in menus:
                    main.append(menu.id)

        main = random.sample(main, 7)
        for el in main:
            plan = WeeklyPlan(menu_id=el, user_id=user_id)
            session.add(plan)
            session.commit()
        return main
    # If it is the first time user logged in
    else:
        res = []
        plan = session.query(WeeklyPlan).filter_by(user_id=user_id).all()
        for el in plan:
            res.append(el.menu_id)
        return res

# Google log in
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
        response = make_response(json.dumps(
            'Failed to upgrade the authorization code.'), 401)
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
        response = make_response(json.dumps(
            "Token's client ID does not match given user ID"), 401)
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
        response = make_response(json.dumps(
            'Current user is already connected.'), 200)
        response.headers['Content-type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # print login_session['username']
    user_id = getUserID(login_session['email'])
    if user_id is None:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id
    # print '~~~~~~~~~~~~~~~~~~~~~~~:('

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

# Log out
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        # reset the user's session.
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['user_id']
        del login_session['email']
        del login_session['picture']
        flash("Successfully Logged out!")
        return redirect(url_for('recipeList'))
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Add new Category
@app.route('/recipes/new/', methods=['GET', 'POST'])
@login_required
def newRecipe():
    if request.method == 'POST':
        valid = session.query(Category)\
            .filter_by(name=request.form['name']).one_or_none()
        if valid is None and request.form['name'].isalpha():
            newCat = Category(
                name=request.form['name'], user_id=login_session['user_id'])
            session.add(newCat)
            session.commit()
            return redirect(url_for('recipeList', user=login_session))
        else:
            abort(400, description="The category name you entered is "
                                   "already being used or it is not valid.")

    else:
        return render_template('newRecipe.html', user=login_session)

# Show Menu List under a specific category.
@app.route('/recipes/<int:category_id>/')
def menuList(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    item = session.query(Menu).filter_by(category_id=category_id).first()
    if item is not None:
        items = session.query(Menu).filter_by(category_id=category_id).all()
    else:
        items =[]
    creator = getUserInfo(category.user_id)
    list = category.name.split()
    # Make sure remove all numbers in their category name (due to database)
    if list[0][0].isdigit():
        del list[0]
        category.name = " ".join(list)
        session.add(category)
        session.commit()
    # If the user is the creator, show the menu page with editing option
    if login_session.get('user_id') == creator.id:
        return render_template('menu.html',
                               category=category,
                               category_id=category_id,
                               items=items, user=login_session)
    # If the user is logged in, show the logout btn on nav bar
    elif 'username' in login_session:
        return render_template('userMenu.html',
                               category=category, category_id=category_id,
                               items=items, user=login_session)
    # If the user is NOT logged in, show the login btn on nav bar
    else:
        return render_template('publicMenu.html',
                               category=category, category_id=category_id,
                               items=items)


# JSON APIs to view Category Information
@app.route('/recipes/<int:category_id>/json/')
def menuListJSON(category_id):
    items = session.query(Menu).filter_by(category_id=category_id).all()
    return jsonify(CategoryList=[item.serialize for item in items])

# Add new menu under a category
@app.route('/recipes/<int:category_id>/new/', methods=['GET', 'POST'])
@login_required
def newMenu(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':
        valid = session.query(Menu)\
            .filter_by(name=request.form['name']).one_or_none()
        # Prevent from making a duplicate
        if valid is None:
            menu = Menu(user_id=login_session['user_id'],
                        name=request.form['name'],
                        picture=request.form['picture'],
                        servings=request.form['servings'],
                        calories=request.form['calories'],
                        hour=request.form['hour'],
                        minute=request.form['minute'],
                        category_id=category_id)
            session.add(menu)
            session.commit()
            addedmenu = session.query(Menu)\
                .filter_by(name=request.form['name']).one()

            amount = request.form.getlist('amount')
            descriptions = request.form.getlist('description')

            # Store ingredients
            for i in range(0, len(descriptions)):
                description = descriptions[i]
                amt = amount[i]
                amt = amt.encode("utf-8")
                description = description.replace('\u00b0', '')
                description = description.replace('\u00a0', '')
                # If the description is empty while amt is filled
                if len(description) == 0 and len(amount[i]) != 0:
                    abort(400,
                          description="You only entered "
                                      "the amount of ingredient: "
                                      "description is missing.")
                # If the description is empty, ignore it.
                elif len(description) == 0:
                    del amount[i]
                    del descriptions[i]
                # If the description is filled.
                else:
                    ingredient = session.query(Ingredient) \
                        .filter_by(description=description).first()
                    if ingredient is None:
                        ingredient = Ingredient(amount=amt,
                                                description=description,
                                                menu_id=addedmenu.id)
                        session.add(ingredient)
                        session.commit()
                    else:
                        # Update amount
                        if ingredient.amount != amt:
                            ingredient.amount = amt
                            session.add(ingredient)
                            session.commit()

            # Ignore all ingredients that a user clicked 'delete'
            amounts = request.form.getlist('delete-amount')
            descriptions = request.form.getlist('delete-description')
            for description in descriptions:
                if len(description) > 0:
                    ingredient = session.query(Ingredient) \
                        .filter_by(description=description).one()
                    session.delete(ingredient)
                    session.commit()

            # Add directions in database
            directions = request.form.getlist('direction')

            for direction in directions:
                # Make sure direction is filled
                if len(direction) > 0:
                    valid = session.query(Direction) \
                        .filter_by(direction=direction).first()
                    # Prevent from making a duplicate
                    if valid is None:
                        direction = Direction(menu_id=addedmenu.id,
                                              direction=direction)
                        session.add(direction)
                        session.commit()
            # Delete the directions from our database
            directions = request.form.getlist('delete-dir')
            for direction in directions:
                if len(direction) > 0:
                    valid = session.query(Direction) \
                        .filter_by(direction=direction).first()
                    # If the data was stored in our database
                    if valid is not None:
                        session.delete(valid)
                        session.commit()

            ingredients = session.query(Ingredient) \
                .filter_by(menu_id=addedmenu.id).all()
            directions = session.query(Direction) \
                .filter_by(menu_id=addedmenu.id).all()
            return redirect(url_for('menuList', category_id=category.id))

        else:
            abort(400,
                  description="The menu name you "
                              "entered is already being used.")
    else:
        return render_template('newMenu.html',
                               category=category,
                               user=login_session)

# Edit Category
@app.route('/recipes/<int:category_id>/edit/', methods=['GET', 'POST'])
@login_required
def editRecipe(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    # The user has to be the creator of this category
    if category.user_id != login_session.get('user_id'):
        return "<script>function myFunction() " \
               "{alert('You are not authorized to edit this category.');}" \
               "</script><body onload='myFunction()'>"
    if request.method == 'POST':
        if request.form['name'].isalpha():
            category.name = request.form['name']
            session.add(category)
            session.commit()
            return redirect(url_for('recipeList'))
        else:
            return "<script>function myFunction() {" \
                   "alert('Please enter the valid category name to edit.');}" \
                   "</script><body onload='myFunction()'>"
    else:
        return render_template('editRecipe.html',
                               category=category,
                               user=login_session)

# Delete Category
@app.route('/recipes/<int:category_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteRecipe(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    # The user has to be the one who created this category.
    if category.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {" \
               "alert('You are not authorized to delete this category.');}" \
               "</script><body onload='myFunction()'>"

    if request.method == 'POST':
        session.delete(category)
        session.commit()
        return redirect(url_for('recipeList'))
    else:
        return render_template('deleteRecipe.html', category=category)

# Show the menu
@app.route('/recipes/<int:category_id>/<int:menu_id>/')
def menuDetails(category_id, menu_id):
    item = session.query(Menu).filter_by(id=menu_id).one()
    menus = session.query(Menu).filter_by(category_id=category_id).all()
    ingredients = session.query(Ingredient).filter_by(menu_id=item.id).first()
    directions = session.query(Direction).filter_by(menu_id=item.id).first()
    creator = getUserInfo(item.user_id)
    category = session.query(Category).filter_by(id=item.category_id).one()

    if directions is not None:
        directions = session.query(Direction).filter_by(menu_id=item.id).all()
    else:
        directions = []
    if ingredients is not None:
        ingredients = session.query(Ingredient)\
            .filter_by(menu_id=item.id).all()
    else:
        ingredients = []
    # If the user is not the creator,
    # the user will not be able to see setting icon
    if creator.id == login_session.get('user_id'):
        return render_template('menuDetails.html',
                               category=category,
                               menus=menus, item=item,
                               ingredients=ingredients,
                               directions=directions,
                               user=login_session)
    # if the user is logged in, logout icon on nav bar
    elif login_session.get('username'):
        return render_template('userMenuDetails.html',
                               category=category,
                               menus=menus, item=item,
                               ingredients=ingredients,
                               directions=directions,
                               user=login_session)
    # if the user is not logged in, login icon on nav bar
    else:
        return render_template('publicMenuDetails.html',
                               category=category,
                               menus=menus,
                               item=item,
                               ingredients=ingredients,
                               directions=directions,
                               user=login_session)


# JSON APIs to view details of menu
@app.route('/recipes/<int:category_id>/<int:menu_id>/json/')
def menuDetailsJSON(category_id, menu_id):
    item = session.query(Menu).filter_by(id=menu_id).one()
    ingredients = session.query(Ingredient).filter_by(menu_id=menu_id).all()
    directions = session.query(Direction).filter_by(menu_id=menu_id).all()
    ingredientsJSON = [ingredient.serialize for ingredient in ingredients]
    directionsJSON = [direction.serialize for direction in directions]
    res = []
    obj = item.serialize
    obj['ingredients'] = ingredientsJSON
    obj['directions'] = directionsJSON
    res.append(obj)
    return jsonify(MenuDetails=res)

# Edit the menu
@app.route('/recipes/<int:category_id>/<int:menu_id>/edit',
           methods=['GET', 'POST'])
@login_required
def editMenu(category_id, menu_id):
    category = session.query(Category).filter_by(id=category_id).one()
    item = session.query(Menu).filter_by(id=menu_id).one()
    ingredients = session.query(Ingredient).filter_by(menu_id=item.id).first()
    directions = session.query(Direction).filter_by(menu_id=item.id).first()
    # The user has to be the one who created this menu.
    if item.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {" \
               "alert('You are not authorized to edit this menu.');}" \
               "</script><body onload='myFunction()'>"

    if directions is not None:
        directions = session.query(Direction).filter_by(menu_id=item.id).all()
    else:
        directions = []
    if ingredients is not None:
        ingredients = session.query(Ingredient)\
            .filter_by(menu_id=item.id).all()
    else:
        ingredients = []
    if request.method == 'POST':
        item.name = request.form['name']
        item.picture = request.form['picture']
        item.servings = request.form['servings']
        item.calories = request.form['calories']
        item.hour = request.form['hour']
        item.minute = request.form['minute']
        session.add(item)
        session.commit()

        amount = request.form.getlist('amount')
        descriptions = request.form.getlist('description')

        # Store ingredients
        for i in range(0, len(descriptions)):
            description = descriptions[i]
            amt = amount[i]
            amt = amt.encode("utf-8")
            description = description.replace('\u00b0', '')
            description = description.replace('\u00a0', '')
            # If the description is empty while amt is filled
            if len(description) == 0 and len(amount[i]) != 0:
                abort(400,
                      description="You only entered "
                                  "the amount of ingredient: "
                                  "description is missing.")
            # If the description is empty, ignore it.
            elif len(description) == 0:
                del amount[i]
                del descriptions[i]
            # If the description is filled.
            else:
                ingredient = session.query(Ingredient)\
                    .filter_by(description=description).first()
                if ingredient is None:
                    ingredient = Ingredient(amount=amt,
                                            description=description,
                                            menu_id=menu_id)
                    session.add(ingredient)
                    session.commit()
                else:
                    # Update amount
                    if ingredient.amount != amt:
                        ingredient.amount = amt
                        session.add(ingredient)
                        session.commit()

        # Ignore all ingredients that a user clicked 'delete'
        amounts = request.form.getlist('delete-amount')
        descriptions = request.form.getlist('delete-description')
        for description in descriptions:
            if len(description) > 0:
                ingredient = session.query(Ingredient)\
                    .filter_by(description=description).one()
                session.delete(ingredient)
                session.commit()

        # Add directions in database
        directions = request.form.getlist('direction')

        for direction in directions:
            # Make sure direction is filled
            if len(direction) > 0:
                valid = session.query(Direction)\
                    .filter_by(direction=direction).first()
                # Prevent from making a duplicate
                if valid is None:
                    direction = Direction(menu_id=menu_id,
                                          direction=direction)
                    session.add(direction)
                    session.commit()
        # Delete the directions from our database
        directions = request.form.getlist('delete-dir')
        for direction in directions:
            if len(direction) > 0:
                valid = session.query(Direction)\
                    .filter_by(direction=direction).first()
                # If the data was stored in our database
                if valid is not None:
                    session.delete(valid)
                    session.commit()

        ingredients = session.query(Ingredient)\
            .filter_by(menu_id=menu_id).all()
        directions = session.query(Direction)\
            .filter_by(menu_id=menu_id).all()
        return redirect(url_for('menuDetails',
                                category_id=category.id,
                                menu_id=menu_id,
                                ingredients=ingredients,
                                directions=directions))
    else:
        return render_template('editMenu.html',
                               ingredients=ingredients,
                               category=category,
                               item=item,
                               directions=directions,
                               user=login_session)


@app.route('/recipes/<int:category_id>/'
           '<int:menu_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteMenu(category_id, menu_id):
    ingredients = session.query(Ingredient).filter_by(menu_id=menu_id).all()
    directions = session.query(Direction).filter_by(menu_id=menu_id).all()
    menu = session.query(Menu).filter_by(id=menu_id).one_or_none()
    category = session.query(Category).filter_by(id=category_id).one()
    # The user has to be the creator of this menu
    if menu.user_id != login_session.get('user_id'):
        return "<script>function myFunction() {" \
               "alert('You are not authorized to delete this menu.');}" \
               "</script><body onload='myFunction()'>"

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
        return render_template('deleteMenu.html',
                               category=category,
                               item=menu,
                               user=login_session)

# if it's a new user, store the user in our database
def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id

# Return the user
def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user

# Check if the user is in our database
def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# When this program runs through python interpreter.
if __name__ == '__main__':
    app.secret_key = "JJINBIN"
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
