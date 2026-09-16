# Pinecone

Pinecone es una base de datos vectorial gestionada en la nube. En lugar de
guardar filas con columnas como una base relacional, guarda vectores
numéricos de alta dimensión (embeddings) y está optimizada para responder una
pregunta muy específica: "de todos los vectores que tengo guardados, ¿cuáles
son los más parecidos a este vector de consulta?". Esa operación se llama
búsqueda por similitud (similarity search) y es la pieza central de cualquier
sistema RAG (Retrieval Augmented Generation).

## Embeddings

Un embedding es la representación numérica de un texto (o una imagen, o
audio) como un vector de números reales, generado por un modelo entrenado
para esa tarea, como `text-embedding-3-small` de OpenAI. La propiedad clave
de los embeddings es que textos con significado parecido quedan cerca en ese
espacio vectorial, aunque usen palabras completamente distintas. Por eso una
búsqueda semántica puede encontrar un fragmento que habla de "contenedores
Docker" a partir de una consulta que dice "aislar procesos con Linux
namespaces", sin que compartan ninguna palabra exacta.

## Índices (indexes)

En Pinecone, un índice es el contenedor principal donde se guardan los
vectores. Al crear un índice hay que definir de antemano su **dimensión**
(la cantidad de números que tiene cada vector, que depende del modelo de
embeddings usado; `text-embedding-3-small` produce vectores de 1536
dimensiones) y su **métrica de distancia**, que define cómo se mide el
parecido entre dos vectores. Todos los vectores que se guarden en ese índice
tienen que tener exactamente esa dimensión.

## Similitud coseno

La métrica de similitud coseno mide el ángulo entre dos vectores, ignorando
su magnitud: dos vectores que apuntan en la misma dirección tienen similitud
coseno cercana a 1, aunque uno sea mucho más "largo" que el otro. Es la
métrica más usada con embeddings de texto, porque lo que importa para el
significado es la dirección del vector, no su longitud. Otras métricas
disponibles son la distancia euclidiana y el producto punto (dot product).

## Pinecone Serverless

Pinecone Serverless es el modelo de despliegue donde no hay que
aprovisionar ni dimensionar manualmente la infraestructura (cuántos "pods" o
qué tamaño de máquina usar): el índice escala automáticamente según la
cantidad de vectores y el tráfico de consultas, y se paga por el uso real
(almacenamiento y lecturas/escrituras) en lugar de por capacidad reservada.
Al crear un índice serverless solo hace falta indicar la dimensión, la
métrica y en qué nube y región se aloja (por ejemplo, AWS `us-east-1`).

## Namespaces

Un namespace es una partición lógica dentro de un mismo índice. Todos los
vectores de un índice comparten la misma dimensión y métrica, pero se pueden
separar en namespaces distintos para, por ejemplo, aislar los documentos de
distintos clientes en un sistema multi-tenant, o separar distintas versiones
de un mismo dataset. Una consulta contra un namespace solo compara contra los
vectores que están dentro de ese namespace, nunca contra los de otro, aunque
convivan en el mismo índice físico. Esto evita tener que crear un índice
completo por cada cliente o cada dataset, que sería mucho más costoso.

## Metadata

Además del vector en sí, cada entrada de Pinecone puede guardar metadata:
pares clave-valor con información adicional sobre ese vector, como el
nombre del archivo de origen, una categoría, o el texto original del
fragmento. La metadata sirve para dos cosas: se puede filtrar la búsqueda
para que solo compare contra vectores que cumplan cierta condición (por
ejemplo, `category = "database"`), y se puede recuperar junto con cada
resultado sin necesidad de consultar otra base de datos aparte para saber
qué contenido representa ese vector.

## Flujo típico de uso

El patrón habitual para usar Pinecone en un sistema RAG es: dividir los
documentos en fragmentos (chunks), generar un embedding por cada fragmento,
subir esos vectores al índice junto con su metadata (incluyendo el texto
original), y en el momento de la consulta, generar el embedding de la
pregunta del usuario y pedirle a Pinecone los vectores más parecidos. Esos
fragmentos recuperados son el contexto que después se le puede pasar a un
modelo de lenguaje para que genere una respuesta fundamentada en ellos.

## Upsert por batches

Subir vectores a Pinecone de a uno por vez es ineficiente: cada llamada de
red tiene un costo fijo de latencia. Por eso el patrón recomendado es hacer
`upsert` en lotes (batches) de un tamaño razonable, típicamente entre 50 y
200 vectores por llamada, en lugar de mandar miles de requests individuales.
"Upsert" significa que si el ID del vector ya existe en el índice, se
actualiza; si no existe, se inserta como nuevo. Por eso conviene usar IDs
deterministicos (por ejemplo, basados en el documento y el número de chunk)
en lugar de IDs aleatorios: así, volver a correr la ingesta sobre el mismo
dataset actualiza los vectores existentes en vez de generar duplicados.

## Búsqueda con filtros de metadata

Una consulta a Pinecone puede combinar la búsqueda por similitud vectorial
con un filtro exacto sobre la metadata, similar a un `WHERE` de SQL pero
aplicado antes o junto con la comparación de vectores. Por ejemplo, se puede
pedir "los 5 vectores más parecidos a esta consulta, pero solo entre los que
tengan `category = "database"`". Esto permite acotar el espacio de búsqueda
sin necesidad de crear un índice o un namespace separado para cada posible
filtro.

## Pinecone vs. una base de datos relacional

Una base relacional como PostgreSQL está optimizada para búsquedas exactas
y relaciones estructuradas entre tablas (`WHERE id = 5`, `JOIN`). Pinecone
está optimizada para un tipo de búsqueda completamente distinto: encontrar
los vectores más *parecidos* a uno dado, en espacios de miles de
dimensiones, algo para lo que un índice B-tree tradicional no sirve. Por eso
en un sistema RAG es común usar las dos juntas: una base relacional para los
datos estructurados de la aplicación, y Pinecone específicamente para la
búsqueda semántica sobre contenido no estructurado (texto, en este caso).
