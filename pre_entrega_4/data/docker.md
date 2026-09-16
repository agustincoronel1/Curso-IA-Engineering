# Docker

Docker es una plataforma para empaquetar aplicaciones junto con todas sus
dependencias (librerías, binarios, configuración) en una unidad portátil
llamada contenedor. La idea central es resolver el problema de "en mi
máquina funciona": si la aplicación corre dentro de un contenedor, se
comporta igual en la laptop del desarrollador, en el servidor de pruebas y en
producción, porque el entorno de ejecución viaja junto con el código.

## Imagen vs contenedor

Estos dos conceptos suelen confundirse pero son distintos:

- Una **imagen** es una plantilla de solo lectura: un conjunto de capas de
  archivos que incluye el sistema operativo base, las dependencias
  instaladas y el código de la aplicación. Una imagen no se ejecuta, se
  almacena y se distribuye.
- Un **contenedor** es una instancia en ejecución de una imagen. A partir de
  la misma imagen se pueden levantar varios contenedores independientes,
  cada uno con su propio estado en memoria, su propio proceso y su propio
  sistema de archivos en capa de escritura (aunque comparten la imagen base
  de solo lectura).

La analogía habitual es la de una clase y un objeto en programación orientada
a objetos: la imagen es la clase, el contenedor es una instancia de esa
clase.

## Dockerfile

Un Dockerfile es un archivo de texto con instrucciones para construir una
imagen paso a paso:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Cada instrucción (`FROM`, `WORKDIR`, `COPY`, `RUN`, `CMD`) genera una capa
nueva en la imagen. Docker cachea las capas que no cambiaron entre builds,
por eso conviene copiar primero los archivos que cambian poco (como
`requirements.txt`) e instalar las dependencias antes de copiar el resto del
código: así, si solo cambia el código de la aplicación, no hace falta
reinstalar todas las dependencias de nuevo.

## Volumes (volúmenes)

Los contenedores son efímeros: si se borran, se pierde todo lo que se haya
escrito en su sistema de archivos. Los volúmenes son la forma de persistir
datos más allá del ciclo de vida de un contenedor. Un volumen es un espacio
de almacenamiento gestionado por Docker (o un directorio del host montado
dentro del contenedor) que sobrevive aunque el contenedor se elimine. Son
imprescindibles para bases de datos: el contenedor de PostgreSQL puede
destruirse y recrearse, pero los datos siguen existiendo en el volumen.

```bash
docker run -v datos_postgres:/var/lib/postgresql/data postgres:16
```

## Ports (puertos)

Un contenedor corre en su propia red aislada por default, así que para poder
acceder a un servicio que corre adentro (como una API en el puerto 8000) hay
que mapear explícitamente un puerto del host a un puerto del contenedor:

```bash
docker run -p 8080:8000 mi-imagen
```

Acá el puerto 8080 de la máquina host queda conectado al puerto 8000 dentro
del contenedor, que es el puerto donde la aplicación está escuchando según el
`EXPOSE 8000` del Dockerfile.

## docker-compose

Cuando una aplicación necesita varios contenedores coordinados (por ejemplo,
una API, una base de datos y un cache), `docker-compose` permite describir
todos los servicios, sus imágenes, sus variables de entorno, sus volúmenes y
las redes entre ellos en un único archivo `docker-compose.yml`, y levantarlos
todos juntos con un solo comando (`docker compose up`).

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - db
  db:
    image: postgres:16
    volumes:
      - datos_postgres:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: secreto

volumes:
  datos_postgres:
```

## Redes en Docker

Por default, Docker crea una red virtual para cada `docker-compose.yml`, y
todos los contenedores definidos ahí pueden comunicarse entre sí usando el
nombre del servicio como si fuera un hostname (en el ejemplo anterior, la
API se conecta a la base de datos usando `db` como host, no `localhost`).
Esto aísla los contenedores del resto de la red del host, y evita que dos
proyectos distintos con contenedores del mismo nombre choquen entre sí.

## Capas y cache de build

Cada instrucción de un Dockerfile genera una capa (layer) inmutable, y
Docker las apila una sobre otra para formar el sistema de archivos final de
la imagen. Cuando se reconstruye una imagen, Docker reutiliza las capas que
no cambiaron (cache de build) y solo reconstruye desde la primera capa que sí
cambió en adelante. Por eso el orden de las instrucciones en el Dockerfile
importa tanto para la velocidad de los builds: poner las instrucciones que
cambian poco (instalar dependencias) antes que las que cambian seguido
(copiar el código fuente) aprovecha mejor ese cache.

## Registries

Una vez construida, una imagen se puede subir a un registry (como Docker Hub
o un registry privado) con `docker push`, y bajarla en cualquier otra
máquina con `docker pull`. Esto es lo que permite que la misma imagen
exacta, con las mismas dependencias, se use en el entorno de desarrollo, en
CI/CD y en producción, eliminando diferencias de entorno entre esas etapas.
