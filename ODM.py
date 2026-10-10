__author__ = 'Pablo Ramos Criado'
__students__ = 'Sara Ayelen Lima Condori, Lidia Gutiérrez López'


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
from typing import Generator, Any, Self
from geojson import Point
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import yaml

def getLocationPoint(address: str) -> Point:
    """ 
    Obtiene las coordenadas de una dirección en formato geojson.Point
    Utilizar la API de geopy para obtener las coordenadas de la direccion
    Cuidado, la API es publica tiene limite de peticiones, utilizar sleeps.

    Parameters
    ----------
        address : str
            direccion completa de la que obtener las coordenadas
    Returns
    -------
        geojson.Point
            coordenadas del punto de la direccion
    """
    location = None
    intentos = 0
    maxIntentos = 5
    for _ in range(maxIntentos):
        try:
            time.sleep(1)
            location = Nominatim(user_agent="P1_Sara_Y_Lidia").geocode(address)
            break
        except GeocoderTimedOut:
            continue

    if location is None:
        raise ValueError(f"No se pudieron obtener coordenadas para la dirección: {address}")

    return Point((location.longitude, location.latitude))


class Model:
    """ 
    Clase de modelo abstracta
    Crear tantas clases que hereden de esta clase como  
    colecciones/modelos se deseen tener en la base de datos.

    Attributes
    ----------
        required_vars : set[str]
            conjunto de atributos requeridos por el modelo
        admissible_vars : set[str]
            conjunto de atributos admitidos por el modelo
        db : pymongo.collection.Collection
            conexion a la coleccion de la base de datos
    
    Methods
    -------
        __setattr__(name: str, value: str | dict) -> None
            Sobreescribe el metodo de asignacion de valores a los 
            atributos del objeto con el fin de controlar qué atributos 
            son modificados y cuando son modificados.
        __getattr__(name: str) -> Any
            Sobreescribe el metodo de acceso a atributos del objeto 
        save()  -> None
            Guarda el modelo en la base de datos
        delete() -> None
            Elimina el modelo de la base de datos
        find(filter: dict[str, str | dict]) -> ModelCursor
            Realiza una consulta de lectura en la BBDD.
            Devuelve un cursor de modelos ModelCursor
        aggregate(pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor
            Devuelve el resultado de una consulta aggregate.
        find_by_id(id: str) -> dict | None
            Busca un documento por su id utilizando la cache y lo devuelve.
            Si no se encuentra el documento, devuelve None.
        init_class(db_collection: pymongo.collection.Collection, required_vars: set[str], admissible_vars: set[str]) -> None
            Inicializa las variables de clase en la inicializacion del sistema.

    """
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _db: pymongo.collection.Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var'))

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        """
        Inicializa el modelo con los valores proporcionados en kwargs
        Comprueba que los valores proporcionados en kwargs son admitidos
        por el modelo y que las atributos requeridos son proporcionadas.

        Parameters
        ----------
            kwargs : dict[str, str | dict]
                diccionario con los valores de las atributos del modelo
        """
        self._data: dict[str, str | dict | list] = {}
        self._modified_vars = set()

        faltan = self._required_vars - kwargs.keys()
        if faltan:
            raise ValueError(f"Faltan atributos requeridos: {sorted(faltan)}")

        permitidos = self._required_vars | self._admissible_vars | {"_id"}
        sobran = kwargs.keys() - permitidos
        if sobran:
            raise ValueError(f"Atributos no admitidos: {sorted(sobran)}")

        self._data.update(kwargs)

        
    def __setattr__(self, name: str, value: str | dict) -> None:
        """
        Sobreescribe el metodo de asignacion de valores a los 
        atributos del objeto con el fin de controlar que atributos 
        son modificados y cuando son modificados.
        """
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return

        if name not in self._required_vars and name not in self._admissible_vars:
            raise AttributeError(f"Atributo no admitido: {name}")

        self._data[name] = value
        self._modified_vars.add(name)

        
    def __getattr__(self, name: str) -> Any:
        """ 
        Sobreescribe el metodo de acceso a atributos del objeto
        __getattr__ solo es llamado cuando no encuentra el atributo
        en el objeto 
        """
        if name in self._internal_vars:
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError
        
    def save(self) -> None:
        """
        Guarda el modelo en la base de datos
        Si el modelo no existe en la base de datos, se crea un nuevo
        documento con los valores del modelo. En caso contrario, se
        actualiza el documento existente con los nuevos valores del
        modelo.
        """
        loc_field = self._location_var
        if "_id" not in self._data:
            documento = dict(self._data)
            if loc_field and loc_field in documento:
                documento[f"{loc_field}_loc"] = getLocationPoint(documento[loc_field])
            self._db.insert_one(documento)
            self._data.update(documento)

        else:
            cambios = {nombre: self._data[nombre] for nombre in self._modified_vars}
            if loc_field and loc_field in cambios:
                cambios[f"{loc_field}_loc"] = getLocationPoint(cambios[loc_field])
            if cambios:
                self._db.update_one({"_id": self._data["_id"]}, {"$set": cambios})
                self._data.update(cambios)

        self._modified_vars.clear()

    def delete(self) -> None:
        """
        Elimina el modelo de la base de datos
        """
        if "_id" in self._data:
            self._db.delete_one({"_id": self._data["_id"]})
            del self._data["_id"]

    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        """ 
        Utiliza el metodo find de pymongo para realizar una consulta
        de lectura en la BBDD.
        find debe devolver un cursor de modelos ModelCursor

        Parameters
        ----------
            filter : dict[str, str | dict]
                diccionario con el criterio de busqueda de la consulta
        Returns
        -------
            ModelCursor
                cursor de modelos
        """ 
        return ModelCursor(cls, cls._db.find(filter))

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor:
        """ 
        Devuelve el resultado de una consulta aggregate. 
        No hay nada que hacer en esta funcion.
        Se utilizara para las consultas solicitadas
        en el segundo proyecto de la practica.

        Parameters
        ----------
            pipeline : list[dict]
                lista de etapas de la consulta aggregate 
        Returns
        -------
            pymongo.command_cursor.CommandCursor
                cursor de pymongo con el resultado de la consulta
        """ 
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 
        #TODO
        pass

    @classmethod
    def init_class(cls, db_collection: pymongo.collection.Collection, indexes:dict[str,str], required_vars: set[str], admissible_vars: set[str]) -> None:
        """ 
        Inicializa los atributos de clase en la inicializacion del sistema.
        Aqui se deben inicializar o asegurar los indices. Tambien se puede
        alguna otra inicialización/comprobaciones o cambios adicionales
        que estime el alumno.

        Parameters
        ----------
            db_collection : pymongo.collection.Collection
                Conexion a la collecion de la base de datos.
            indexes: Dict[str,str]
                Set de indices y tipo de indices para la coleccion
            required_vars : set[str]
                Set de atributos requeridos por el modelo
            admissible_vars : set[str] 
                Set de atributos admitidos por el modelo
        """
        cls._db = db_collection
        cls._required_vars = required_vars
        cls._admissible_vars = admissible_vars
        cls._location_var = None

        for field, index_type in (indexes or {}).items():
            if index_type == "unique":
                cls._db.create_index([(field, pymongo.ASCENDING)], unique=True)
            elif index_type == "asc":
                cls._db.create_index([(field, pymongo.ASCENDING)])
            elif index_type == "geosphere":
                cls._location_var = field
                cls._db.create_index([(f"{field}_loc", pymongo.GEOSPHERE)])




class ModelCursor:
    """ 
    Cursor para iterar sobre los documentos del resultado de una
    consulta. Los documentos deben ser devueltos en forma de objetos
    modelo.

    Attributes
    ----------
        model_class : Model
            Clase para crear los modelos de los documentos que se iteran.
        cursor : pymongo.cursor.Cursor
            Cursor de pymongo a iterar

    Methods
    -------
        __iter__() -> Generator
            Devuelve un iterador que recorre los elementos del cursor
            y devuelve los documentos en forma de objetos modelo.
    """

    def __init__(self, model_class: Model, cursor: pymongo.cursor.Cursor):
        """
        Inicializa el cursor con la clase de modelo y el cursor de pymongo

        Parameters
        ----------
            model_class : Model
                Clase para crear los modelos de los documentos que se iteran.
            cursor: pymongo.cursor.Cursor
                Cursor de pymongo a iterar
        """
        self.model = model_class
        self.cursor = cursor
    
    def __iter__(self) -> Generator:
        """
        Devuelve un iterador que recorre los elementos del cursor
        y devuelve los documentos en forma de objetos modelo.
        Utilizar yield para generar el iterador
        Utilizar la funcion next para obtener el siguiente documento del cursor
        Utilizar alive para comprobar si existen mas documentos.
        """
        while self.cursor.alive:
            try:
                documento = next(self.cursor)
            except StopIteration:
                break
            yield self.model(**documento)


def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals()) -> None:
    """ 
    Declara las clases que heredan de Model para cada uno de los 
    modelos de las colecciones definidas en definitions_path.
    Inicializa las clases de los modelos proporcionando los indices y 
    atributos admitidos y requeridos para cada una de ellas y la conexión a la
    collecion de la base de datos.
    
    Parameters
    ----------
        definitions_path : str
            ruta al fichero de definiciones de modelos
        mongodb_uri : str
            uri de conexion a la base de datos
        db_name : str
            nombre de la base de datos
    """
    # Inicializar base de datos
    client = MongoClient(mongodb_uri)
    db = client[db_name]

    # Declarar tantas clases modelo colecciones existan en la base de datos
    with open(definitions_path, "r", encoding="utf-8") as f:
        definitions = yaml.safe_load(f) or {}

    for model_name, definition in definitions.items():
        required_vars = set(definition.get("required_vars") or [])
        admissible_vars = set(definition.get("admissible_vars") or [])

        indexes = {}
        for field in definition.get("regular_indexes") or []:
            indexes[field] = "asc"
        for field in definition.get("unique_indexes") or []:
            indexes[field] = "unique"
        location_field = definition.get("location_index")
        if location_field:
            indexes[location_field] = "geosphere"
            admissible_vars.add(f"{location_field}_loc")
    
        
        scope[model_name] = type(model_name, (Model,),{})
        
        scope[model_name].init_class(
            db_collection=db[model_name],
            indexes=indexes,
            required_vars=required_vars,
            admissible_vars=admissible_vars
        )

if __name__ == '__main__':
    initApp(db_name="abd_test")
    Recinto._db.delete_many({})

    # Crear modelo
    r = Recinto(nombre="Wizink Center", direccion="Av. Felipe II, Madrid", aforo=17000, zonas=[{"nombre": "Pista", "asientos": 5000}])

    # Asignar nuevo valor a variable admitida
    r.aforo = 17453
    print("Modificadas:", r._modified_vars)

    # Asignar nuevo valor a variable no admitida
    try:
        r.color = "rojo"
    except AttributeError as e:
        print("Rechazado:", e)

    # Guardar (inserta, con direccion_loc)
    r.save()
    print("Guardado:", Recinto._db.find_one({"_id": r._id}))

    # save no pisa campos que no se modificaron
    Recinto._db.update_one({"_id": r._id}, {"$set": {"servicios": ["bar"]}})  # cambio "externo"
    r.aforo = 18000
    r.save()
    print("servicios sigue ahí:", Recinto._db.find_one({"_id": r._id}).get("servicios"))

    # Buscar con find y obtener el primer documento
    primero = next(iter(Recinto.find({"nombre": "Wizink Center"})))
    print(type(primero), primero.aforo)

    # Modificar y guardar
    primero.aforo = 19000
    primero.save()
    print("Aforo en la base:", Recinto._db.find_one({"_id": primero._id})["aforo"])

    # Borrar
    primero.delete()
    print("Documentos restantes:", Recinto._db.count_documents({}))

    # Dirección inexistente: error y nada guardado
    mala = Recinto(nombre="Sala Fantasma", direccion="asdkjhasdkjh qwoeiuqwoei", aforo=100, zonas=[])
    try:
        mala.save()
    except ValueError as e:
        print("OK, ValueError:", e)
    print("Salas fantasma guardadas:", Recinto._db.count_documents({"nombre": "Sala Fantasma"}))

    Recinto._db.database.client.drop_database("abd_test")

