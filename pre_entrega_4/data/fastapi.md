# FastAPI

FastAPI es un framework web para Python pensado para construir APIs. Se apoya
en las anotaciones de tipos de Python (type hints) para hacer dos cosas al
mismo tiempo: validar los datos que entran y salen de la API, y generar
documentación interactiva automáticamente. Está construido sobre Starlette
(para la parte web) y Pydantic (para la validación de datos).

## Endpoints

Un endpoint es una función de Python asociada a una ruta HTTP y un método
(GET, POST, PUT, DELETE, etc). Se define con un decorador:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/usuarios/{usuario_id}")
def obtener_usuario(usuario_id: int):
    return {"id": usuario_id}
```

Cada endpoint puede recibir parámetros de ruta (como `usuario_id` en el
ejemplo), parámetros de query string, un cuerpo de request (body) y headers.
FastAPI convierte automáticamente estos valores al tipo declarado en la
función. Si `usuario_id` llega como texto no numérico, FastAPI rechaza la
petición antes de que el código de la función se ejecute.

## Validación con Pydantic

FastAPI usa modelos de Pydantic (`BaseModel`) para describir el cuerpo de las
peticiones. Cuando un cliente manda un JSON que no cumple con el esquema
declarado, FastAPI responde automáticamente con un error 422 (Unprocessable
Entity) y un detalle de qué campo falló, sin que el desarrollador tenga que
escribir ese chequeo a mano. Esta combinación (tipos de Python + Pydantic) es
la razón principal por la que FastAPI evita gran parte del código repetitivo
de validación manual que existe en otros frameworks.

## Códigos de estado HTTP

FastAPI permite declarar explícitamente qué código HTTP debe devolver cada
endpoint, y usa códigos sensatos por default:

- `200 OK`: la petición se resolvió correctamente.
- `201 Created`: se creó un recurso nuevo (típico en un POST).
- `404 Not Found`: el recurso pedido no existe.
- `422 Unprocessable Entity`: el body o los parámetros no pasaron la
  validación de Pydantic.
- `500 Internal Server Error`: un error no controlado en el servidor.

Se pueden declarar con el parámetro `status_code` del decorador o lanzando una
`HTTPException` con el código y el detalle deseado.

## Programación asíncrona (async/await)

FastAPI soporta funciones síncronas (`def`) y asíncronas (`async def`) como
endpoints. Cuando un endpoint hace operaciones de entrada/salida que implican
esperar (una consulta a una base de datos, una llamada HTTP a otro servicio),
conviene declararlo como `async def` y usar `await` sobre esas operaciones.
Esto le permite al servidor atender otras peticiones mientras espera una
respuesta lenta, en lugar de quedar bloqueado. FastAPI corre sobre un
servidor ASGI (como Uvicorn), que es justamente el estándar que reemplaza a
WSGI para poder manejar concurrencia con async/await.

## Dependency Injection (inyección de dependencias)

FastAPI tiene un sistema de inyección de dependencias basado en la función
`Depends`. Una dependencia es simplemente una función (o una clase) que
FastAPI ejecuta antes del endpoint y cuyo resultado se pasa como argumento.
Sirve para reutilizar lógica común entre varios endpoints, como:

- Obtener el usuario autenticado a partir de un token.
- Abrir y cerrar una sesión de base de datos.
- Validar permisos antes de ejecutar la lógica del endpoint.

```python
from fastapi import Depends

def obtener_sesion_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/items/")
def listar_items(db=Depends(obtener_sesion_db)):
    return db.query(Item).all()
```

La inyección de dependencias hace que la lógica transversal (autenticación,
conexión a la base de datos, paginación) quede desacoplada del cuerpo del
endpoint y sea fácil de testear reemplazando la dependencia por una versión
falsa (mock) en los tests.

## Documentación automática

Como cada endpoint ya declara sus tipos de entrada y salida, FastAPI genera
automáticamente documentación interactiva en `/docs` (Swagger UI) y `/redoc`
(ReDoc), sin que el desarrollador tenga que escribir ni mantener un archivo
de especificación aparte. Esa documentación se genera a partir del estándar
OpenAPI.

## Middlewares

Un middleware es una función que se ejecuta en cada request, antes o después
de que llegue al endpoint correspondiente. Sirve para lógica que aplica a
toda la aplicación por igual, como agregar headers de CORS, medir el tiempo
de respuesta, loguear cada petición o comprimir la respuesta. Se registran
con `app.add_middleware(...)` o con el decorador `@app.middleware("http")`,
y forman una cadena: cada request pasa por todos los middlewares en orden
antes de llegar al endpoint, y la response vuelve a pasar por ellos en orden
inverso.

## Routers

Cuando una aplicación crece, no conviene declarar todos los endpoints en un
único archivo. `APIRouter` permite agrupar endpoints relacionados (por
ejemplo, todos los que tienen que ver con usuarios) en un módulo aparte, y
después incluirlos en la aplicación principal con `app.include_router(...)`.
Esto mantiene el código organizado por dominio en vez de por tipo de
operación HTTP, y permite aplicar un prefijo de ruta y dependencias comunes
a todo un grupo de endpoints de una sola vez.

## Manejo de errores

FastAPI permite capturar excepciones de forma centralizada con
`@app.exception_handler(TipoDeExcepcion)`, para transformar cualquier error
de negocio en una respuesta HTTP consistente sin tener que repetir el
`try/except` en cada endpoint. La excepción `HTTPException` es la forma
estándar de cortar la ejecución de un endpoint y devolver un código de
estado y un mensaje de error específicos, por ejemplo
`raise HTTPException(status_code=404, detail="Usuario no encontrado")`.
