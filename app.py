
import streamlit as st
import pyodbc
import pickle
import requests
import pandas as pd
from textblob import TextBlob
from fuzzywuzzy import process, fuzz
from googletrans import Translator
import speech_recognition as sr
from langdetect import detect
from spellchecker import SpellChecker
import datetime



# Veritabanı bağlantısı
# Database connection
connection = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};'
                            'SERVER=DESKTOP-L3P1LOQ\\SQLEXPRESS;'
                            'DATABASE=MovieRecommendationSystem;'
                            'Trusted_Connection=yes;')
cursor = connection.cursor()


# Kullanıcı Kayıt
# User Register

def register_user(name, email, password):
    try:
        query = "INSERT INTO [User] (name, email, password) VALUES (?, ?, ?)"
        cursor.execute(query, (name, email[:50], password))
        connection.commit()
        st.success("Registration successful! Please login to access the recommendation system.")
    except Exception as e:
        st.error(f"Error during registration: {str(e)}")


def user_registration_page():
    st.title("User Registration")
    name = st.text_input("Name")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        register_user(name, email, password)
        st.markdown("[Go to Login](#user-login)")

# Kullanıcı girişi
# User Login

def user_login(email, password):
    query = "SELECT * FROM [User] WHERE email=? AND password=?"
    cursor.execute(query, (email, password))
    user = cursor.fetchone()
    return user


def user_login_page():
    st.title("User Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = user_login(email, password)
        if user:
            st.success("Login successful!")
            st.session_state['logged_in'] = True
            st.session_state['user'] = user
            st.experimental_rerun()
        else:
            st.error("Invalid email or password")
   
  # Poster verisi
  # Poster data

def fetch_poster(movie_id):
    # api_key alanına TMDB üzerinden kendi api key'inizi almanız gerekiyor.
    # You need to get your own api key from TMDB in the api_key field.
    url = "https://api.themoviedb.org/3/movie/{}?api_key=9a668921c7b7d3270d48cc789bf44b91&language=en-US".format(movie_id)
    data = requests.get(url)
    data = data.json()
    poster_path = data['poster_path']
    full_path = "http://image.tmdb.org/t/p/w500/" + poster_path
    return full_path

# Film Detayları
# Movie Details

def fetch_movie_details(movie_id):
    url = "https://api.themoviedb.org/3/movie/{}?api_key=9a668921c7b7d3270d48cc789bf44b91&language=en-US".format(movie_id)
    data = requests.get(url)
    data = data.json()
    return data

def display_movie_details(movie_id):
    details = fetch_movie_details(movie_id)
   
    if details:
        st.image("http://image.tmdb.org/t/p/w500/" + details['poster_path'], width=200)
        st.subheader(details['title'])
        st.text(f"Release Date: {details['release_date']}")
        st.text(f"Rating: {details['vote_average']}")
        st.text(f"Runtime: {details['runtime']} minutes")
        st.caption(f"Overview: {details['overview']}")
    
        
# Film verileri
# Movie data
movies = pickle.load(open('artifacts/movie_list.pkl', 'rb'))
similarity = pickle.load(open('artifacts/similarity.pkl', 'rb'))


#Translator ve SpellChecker
translator = Translator()
spell = SpellChecker()


def translate_text(text, dest='en'):
    try:
        translation = translator.translate(text, dest=dest)
        return translation.text
    except Exception as e:
        return text


def correct_spelling(text, choices):
    corrected_text = str(TextBlob(text).correct())
    closest_match = process.extractOne(corrected_text, choices, scorer=fuzz.token_sort_ratio)
    return closest_match[0]

# Film önerisi
# Movie Recommendation

def recommend(movie):
    movie = translate_text(movie, 'en')
    movie = correct_spelling(movie, movies['title'].values)
    index = movies[movies['title'] == movie].index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_movies_name = []
    recommended_movies_poster = []
    recommended_movies_similarity = []
    show_movie_details = []
    for i in distances[1:6]:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movies_poster.append(fetch_poster(movie_id))
        recommended_movies_name.append(movies.iloc[i[0]].title)
        recommended_movies_similarity.append(i[1])
        show_movie_details.append(display_movie_details(movie_id))
    return recommended_movies_name, recommended_movies_poster, recommended_movies_similarity, show_movie_details



def detect_language(text):
    try:
        return detect(text)
    except:
        return 'en'


def recognize_speech():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("Speak now...")
        audio = r.listen(source)
        try:
            text = r.recognize_google(audio, language="tr-TR, en-US")
            return text
        except sr.UnknownValueError:
            st.error("Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            st.error(f"Could not request results from Google Speech Recognition service; {e}")
    return ""

# Öneri Geçmişi
# Recommendation History

def save_recommendation(user_id, movie_title, recommendations):
    try:
        timestamp = datetime.datetime.now()
        query = "INSERT INTO [RecommendationHistory] (user_id, movie_title, recommendations, timestamp) VALUES (?, ?, ?, ?)"
        cursor.execute(query, (user_id, movie_title, recommendations, timestamp))
        connection.commit()
    except Exception as e:
        st.error(f"Error saving recommendation: {str(e)}")


def get_recommendation_history(user_id):
    try:
        query = "SELECT movie_title, recommendations, timestamp FROM [RecommendationHistory] WHERE user_id=? ORDER BY timestamp DESC"
        cursor.execute(query, (user_id,))
        history = cursor.fetchall()
        return history
    except Exception as e:
        st.error(f"Error retrieving recommendation history: {str(e)}")
        return []


if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'selected_movie' not in st.session_state:
    st.session_state.selected_movie = ''
if 'selected_actor' not in st.session_state:
    st.session_state.selected_actor = ''
if 'selected_director' not in st.session_state:
    st.session_state.selected_director = ''

# Konuştuğum Türkçe kelimeyi İngilizce'ye çeviriyor.
# It translates the Turkish word I speak into English.
def update_movie():
    text = recognize_speech()
    if text:
        lang = detect_language(text)
        if lang == 'tr':
            st.session_state.selected_movie = translate_text(text, 'en')
        else:
            st.session_state.selected_movie = text


def update_actor():
    text = recognize_speech()
    if text:
        lang = detect_language(text)
        if lang == 'tr':
            st.session_state.selected_actor = translate_text(text, 'en')
        else:
            st.session_state.selected_actor = text


def update_director():
    text = recognize_speech()
    if text:
        lang = detect_language(text)
        if lang == 'tr':
            st.session_state.selected_director = translate_text(text, 'en')
        else:
            st.session_state.selected_director = text

# Aktör Bazlı Öneri
# Actor Based Recommendation

def recommend_actors(actors):
    # Girilen aktör ismine en yakın eşleşmeyi bul.
    # Find the closest match to the entered actor name.
    closest_match = process.extractOne(actors, set(', '.join(movies['cast'].values).split(', ')))
    closest_actor = closest_match[0]
    # Eşleşen aktör için öneri yap.
    # Make a suggestion for matching actor.
    actor_movies = movies[movies['cast'].str.contains(closest_actor, na=False)]
    if actor_movies.empty:
        return [], [], []
    index = actor_movies.index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_movies_name = actor_movies['title'].values
    recommended_movies_poster = [fetch_poster(movie_id) for movie_id in actor_movies['movie_id'].values]
    show_movie_details = [display_movie_details(movie_id) for movie_id in actor_movies['movie_id'].values[:5]]
    
    
    recommended_movies_similarity = []
    for i in distances[1:6]:
        movie_id = movies.iloc[i[0]].movie_id
       
        recommended_movies_similarity.append(i[1])
        
    return recommended_movies_name, recommended_movies_poster, recommended_movies_similarity, show_movie_details


# Yönetmen Bazlı Öneri
# Director Based Recommendation
def recommend_movies_by_director(director):
    director = correct_spelling(director, set(', '.join(movies['crew'].values).split(', ')))
    director_movies = movies[movies['crew'].str.contains(director, na=False)]
    if director_movies.empty:
        return [], [], []
    index = director_movies.index[0]
    distances = sorted(list(enumerate(similarity[index])), reverse=True, key=lambda x: x[1])
    recommended_movies_name = director_movies['title'].values
    recommended_movies_poster = [fetch_poster(movie_id) for movie_id in director_movies['movie_id'].values]
    show_movie_details = [display_movie_details(movie_id) for movie_id in director_movies['movie_id'].values[:5]]
    recommended_movies_similarity = []
    
    for i in distances[1:6]:
        movie_id = movies.iloc[i[0]].movie_id
        recommended_movies_similarity.append(i[1])
        
    return recommended_movies_name, recommended_movies_poster, recommended_movies_similarity,show_movie_details



# Ana Sayfa
# Main Page

def main_page():
    st.title("Movie Recommendation System")
    user_name = st.session_state['user'][1]
    user_id = st.session_state['user'][0]
    st.sidebar.write(f"Welcome, {user_name}!")

    movie_list = movies['title'].values
    selected_movie = st.text_input('Type or Speak a Movie to Get Movie Recommendations', key='movie_input', value=st.session_state.selected_movie)

    col1, col2 = st.columns([4, 10])
    with col1:
        show_recommendation_button = st.button('Show Recommendation', key='button2')
    with col2:
        voice_input_button = st.button("🎤", key='voice_button', on_click=update_movie)

    if show_recommendation_button:
        recommended_movies_name, recommended_movies_poster, recommended_movies_similarity, show_movie_details = recommend(selected_movie)
        save_recommendation(user_id, selected_movie, ', '.join(recommended_movies_name[:5]))
        # distances değişkenini tanımlıyoruz.
        # We define the distances variable.
        col1, col2, col3, col4, col5 = st.columns(5)
        st.text(f"Similarity: {recommended_movies_similarity}")
        
        with col1:
            st.text(recommended_movies_name[0])
            st.image(recommended_movies_poster[0])
           
        with col2:
            st.text(recommended_movies_name[1])
            st.image(recommended_movies_poster[1])
       
        with col3:
            st.text(recommended_movies_name[2])
            st.image(recommended_movies_poster[2])
           
        with col4:
            st.text(recommended_movies_name[3])
            st.image(recommended_movies_poster[3])
          
        with col5:
            st.text(recommended_movies_name[4])
            st.image(recommended_movies_poster[4])
           

    selected_actor = st.text_input('Type or Speak an Actor to Get Movie Recommendations', key='actor_input', value=st.session_state.selected_actor)

    col1, col2 = st.columns([4, 10])
    with col1:
        show_recommendation_button = st.button('Show Recommendation', key='button3')
    with col2:
        voice_input_button = st.button("🎤", key='voice_button_actor', on_click=update_actor)

    if show_recommendation_button:
        recommended_movies_name, recommended_movies_poster, recommended_movies_similarity, show_movie_details = recommend_actors(selected_actor)
        save_recommendation(user_id, selected_actor, ', '.join(recommended_movies_name[:5]))
        col1, col2, col3, col4, col5 = st.columns(5)
        st.text(f"Similarity: {recommended_movies_similarity}")
        with col1:
            st.text(recommended_movies_name[0])
            st.image(recommended_movies_poster[0])
        with col2:
            st.text(recommended_movies_name[1])
            st.image(recommended_movies_poster[1])
        with col3:
            st.text(recommended_movies_name[2])
            st.image(recommended_movies_poster[2])
        with col4:
            st.text(recommended_movies_name[3])
            st.image(recommended_movies_poster[3])
        with col5:
            st.text(recommended_movies_name[4])
            st.image(recommended_movies_poster[4])

    selected_director = st.text_input('Type or Speak a Director to Get Movie Recommendations', key='director_input', value=st.session_state.selected_director)

    col1, col2 = st.columns([4, 10])
    with col1:
        show_recommendation_button = st.button('Show Recommendation', key='button4')
    with col2:
        voice_input_button = st.button("🎤", key='voice_button_director', on_click=update_director)

    if show_recommendation_button:
        recommended_movies_name, recommended_movies_poster, recommended_movies_similarity, show_movie_details = recommend_movies_by_director(selected_director)
        save_recommendation(user_id, selected_director, ', '.join(recommended_movies_name[:5]))
        col1, col2, col3, col4, col5 = st.columns(5)
        st.text(f"Similarity: {recommended_movies_similarity}")
        with col1:
            st.text(recommended_movies_name[0])
            st.image(recommended_movies_poster[0])
        with col2:
            st.text(recommended_movies_name[1])
            st.image(recommended_movies_poster[1])
        with col3:
            st.text(recommended_movies_name[2])
            st.image(recommended_movies_poster[2])
        with col4:
            st.text(recommended_movies_name[3])
            st.image(recommended_movies_poster[3])
        with col5:
            st.text(recommended_movies_name[4])
            st.image(recommended_movies_poster[4])

    if st.button('View Recommendation History'):
        history = get_recommendation_history(user_id)
        if history:
            for record in history:
                st.write(f"Search: {record[0]}")
                st.write(f"Recommendations: {record[1]}")
                st.write(f"Timestamp: {record[2]}")
                st.write("---")
        else:
            st.write("No recommendation history found.")

            

def main():
    st.sidebar.title("Navigation")
    menu = ["Home", "Login", "Register"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Home":
        if st.session_state['logged_in']:
            main_page()
        else:
            st.write("Please login to access the movie recommendation system.")
            user_login_page()
    elif choice == "Login":
        user_login_page()
    elif choice == "Register":
        user_registration_page()  
   

if __name__ == "__main__":
    main()





