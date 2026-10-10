from datetime import datetime
from bson import json_util
from pymongo import MongoClient
from ODM import initApp

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "abd"


def cargarDatos():
    recintos = {}
    for datos in [
        dict(nombre="WiZink Center", direccion="Avenida de Felipe II, Madrid", aforo=17000,
             zonas=[{"nombre": "Pista", "asientos": 6000}, {"nombre": "Grada", "asientos": 11000}],
             servicios=["bar", "guardarropa"]),
        dict(nombre="Palau Sant Jordi", direccion="Passeig Olímpic 5, Barcelona", aforo=17960,
             zonas=[{"nombre": "Pista", "asientos": 7000}, {"nombre": "Grada", "asientos": 10960}]),
        dict(nombre="Estadio Santiago Bernabéu", direccion="Avenida de Concha Espina 1, Madrid",
             aforo=78000, zonas=[{"nombre": "Campo", "asientos": 18000}, {"nombre": "Grada", "asientos": 60000}],
             servicios=["bar", "parking", "accesibilidad"]),
    ]:
        recinto = Recinto(**datos)
        recinto.save()
        recintos[recinto.nombre] = recinto._id

    artistas = {}
    for datos in [
        dict(nombre="Rosalía", generos=["flamenco", "pop"], pais_origen="España", anio_inicio=2017),
        dict(nombre="Coldplay", generos=["rock", "pop"], pais_origen="Reino Unido", anio_inicio=1996),
        dict(nombre="Bad Bunny", generos=["reguetón", "trap"], pais_origen="Puerto Rico", anio_inicio=2016),
        dict(nombre="Taylor Swift", generos=["pop", "country"], pais_origen="Estados Unidos", anio_inicio=2006),
    ]:
        artista = Artista(**datos)
        artista.save()
        artistas[artista.nombre] = artista._id

    for datos in [
        dict(titulo="Motomami World Tour", artistas=[artistas["Rosalía"]],
             recinto=recintos["WiZink Center"], fecha_hora=datetime(2022, 7, 23, 21, 30),
             precio_por_zona=[{"zona": "Pista", "precio": 65.0}, {"zona": "Grada", "precio": 45.0}],
             entradas_vendidas=16500),
        dict(titulo="The Eras Tour", artistas=[artistas["Taylor Swift"]],
             recinto=recintos["Estadio Santiago Bernabéu"], fecha_hora=datetime(2024, 5, 29, 20, 0),
             precio_por_zona=[{"zona": "Campo", "precio": 120.0}, {"zona": "Grada", "precio": 85.0}],
             entradas_vendidas=76000),
        dict(titulo="Noche Latina", artistas=[artistas["Bad Bunny"], artistas["Rosalía"]],
             recinto=recintos["Palau Sant Jordi"], fecha_hora=datetime(2027, 3, 12, 21, 0),
             precio_por_zona=[{"zona": "Pista", "precio": 90.0}, {"zona": "Grada", "precio": 60.0}]),
    ]:
        Evento(**datos).save()

    for datos in [
        dict(nombre="Marta Ruiz", correo="marta@example.com", fecha_alta=datetime(2023, 2, 10),
             direccion="Calle de Alcalá 100, Madrid", preferencias_genero=["pop", "flamenco"]),
        dict(nombre="Jordi Puig", correo="jordi@example.com", fecha_alta=datetime(2024, 9, 3),
             direccion="Carrer de Balmes 50, Barcelona", preferencias_genero=["rock"]),
        dict(nombre="Carmen León", correo="carmen@example.com", fecha_alta=datetime(2025, 1, 20)),
    ]:
        Asistente(**datos).save()


def volcarColecciones(carpeta="."):
    db = MongoClient(MONGO_URI)[DB_NAME]
    for nombre in db.list_collection_names():
        with open(f"{carpeta}/{nombre}.json", "w", encoding="utf-8") as f:
            f.write(json_util.dumps(list(db[nombre].find()), indent=2, ensure_ascii=False))
        print("Volcado:", f"{nombre}.json")


if __name__ == "__main__":
    MongoClient(MONGO_URI).drop_database(DB_NAME)
    initApp(db_name=DB_NAME, scope=globals())
    cargarDatos()
    volcarColecciones()