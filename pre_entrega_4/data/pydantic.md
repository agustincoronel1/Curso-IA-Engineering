# Pydantic

Pydantic es una librería de Python para validar datos usando anotaciones de
tipos estándar. En lugar de escribir a mano los chequeos de "este campo tiene
que ser un entero mayor a cero" o "este campo es obligatorio", se declara un
modelo de datos con tipos, y Pydantic se encarga de validar, convertir y
reportar errores automáticamente. Es la base de la validación de datos en
FastAPI, pero también se usa de forma independiente en scripts, pipelines de
datos o cualquier lugar donde haga falta confiar en la forma de los datos que
entran al sistema.

## BaseModel

La pieza central de Pydantic es `BaseModel`. Cualquier modelo de datos se
define heredando de esta clase:

```python
from pydantic import BaseModel

class Usuario(BaseModel):
    id: int
    nombre: str
    email: str
    activo: bool = True
```

Al instanciar `Usuario(id="42", nombre="Ana", email="ana@mail.com")`,
Pydantic valida cada campo contra su tipo declarado. El string `"42"` se
convierte automáticamente a `int` porque es una conversión segura; en cambio,
si `id` llegara como `"abc"`, Pydantic lanza una `ValidationError` con un
mensaje claro indicando qué campo falló y por qué.

## Tipos soportados

Pydantic soporta los tipos nativos de Python (`int`, `str`, `float`, `bool`,
`list`, `dict`, `date`, `datetime`), tipos genéricos (`list[str]`,
`dict[str, int]`), `Optional` para campos que pueden ser `None`, `Enum` para
valores restringidos a un conjunto fijo, y modelos anidados (un `BaseModel`
puede tener como campo otro `BaseModel`). Esto permite describir estructuras
de datos complejas, como un pedido que contiene una lista de items, cada uno
con su propio modelo.

## Field

`Field` se usa para agregar metadata y restricciones extra a un campo, más
allá del tipo:

```python
from pydantic import BaseModel, Field

class Producto(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    precio: float = Field(gt=0, description="Precio en dólares, debe ser positivo")
    stock: int = Field(default=0, ge=0)
```

Con `Field` se pueden declarar valores mínimos y máximos (`gt`, `ge`, `lt`,
`le`), longitudes de strings, valores por default, alias para el nombre del
campo en JSON, y descripciones que después FastAPI reutiliza para generar la
documentación automática.

## Validadores personalizados

Cuando una regla de negocio no se puede expresar solo con tipos, Pydantic
permite declarar validadores propios con el decorador `field_validator` (o
`model_validator` para validar la combinación de varios campos a la vez):

```python
from pydantic import BaseModel, field_validator

class Usuario(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor):
        if "@" not in valor:
            raise ValueError("email inválido")
        return valor
```

## Serialización

Además de validar datos de entrada, Pydantic sirve para serializar objetos de
Python a JSON (y viceversa). Un modelo se puede convertir a diccionario con
`.model_dump()` o a un string JSON con `.model_dump_json()`. Esto es lo que
usa FastAPI para transformar automáticamente los objetos que devuelve un
endpoint en la respuesta HTTP en formato JSON, respetando los tipos y los
nombres de campo declarados en el modelo.

## Por qué importa la validación temprana

La idea central detrás de Pydantic es fallar rápido y con un mensaje claro:
si los datos que entran a un sistema no cumplen el esquema esperado, es mejor
rechazarlos en el borde del sistema (por ejemplo, al recibir una request
HTTP) que dejar que un dato mal formado se propague por la lógica de negocio
y produzca un error confuso más adelante, lejos de donde se originó el
problema real.

## Modelos anidados

Un campo de un `BaseModel` puede ser, a su vez, otro `BaseModel`. Esto
permite describir estructuras jerárquicas completas, como un pedido que
contiene una lista de items, y cada item con su propio precio y cantidad:

```python
class Item(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)

class Pedido(BaseModel):
    id: int
    items: list[Item]
    direccion_envio: str
```

Cuando se valida un `Pedido`, Pydantic valida recursivamente cada `Item` de
la lista, así que un item con `cantidad=0` hace fallar la validación del
pedido completo, con un mensaje de error que indica exactamente en qué
posición de la lista y en qué campo está el problema.

## ValidationError y manejo de errores

Cuando falla la validación, Pydantic lanza una `ValidationError` que no es un
simple string: contiene una lista estructurada de errores, cada uno con la
ruta del campo que falló (`loc`), el tipo de error y un mensaje legible. Esto
permite, por ejemplo, que FastAPI arme automáticamente una respuesta 422 con
el detalle de cada campo inválido, o que una aplicación de línea de comandos
le muestre al usuario exactamente qué corregir en el archivo de
configuración que intentó cargar.

## Configuración de modelos con model_config

Cada `BaseModel` puede ajustar su comportamiento con el atributo
`model_config`, por ejemplo para prohibir campos extra no declarados en el
esquema (`extra="forbid"`), para permitir poblar el modelo a partir de
atributos de un objeto de ORM en lugar de un diccionario
(`from_attributes=True`), o para que los strings se limpien de espacios en
blanco automáticamente. Esta configuración centraliza reglas que, si no,
habría que repetir campo por campo.
