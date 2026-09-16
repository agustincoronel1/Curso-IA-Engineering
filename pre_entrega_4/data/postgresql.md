# PostgreSQL

PostgreSQL es un sistema de gestión de bases de datos relacionales de código
abierto. Los datos se organizan en tablas con filas y columnas, y se
consultan usando SQL. A diferencia de una base NoSQL, PostgreSQL exige un
esquema definido de antemano (tipos de columna, claves foráneas, restricciones
de unicidad), lo que la hace especialmente adecuada para datos con relaciones
claras entre entidades, como usuarios, pedidos y productos.

## Transacciones y ACID

Una transacción es un conjunto de operaciones (inserts, updates, deletes) que
se ejecutan como una sola unidad: o se aplican todas, o no se aplica ninguna.
PostgreSQL garantiza las propiedades ACID en cada transacción:

- **Atomicidad**: la transacción se aplica completa o no se aplica nada. Si
  falla a mitad de camino, se revierte (`ROLLBACK`) y la base queda como si
  nunca hubiera empezado.
- **Consistencia**: la transacción lleva la base de datos de un estado válido
  a otro estado válido, respetando todas las restricciones definidas
  (claves foráneas, `NOT NULL`, `CHECK`).
- **Aislamiento (Isolation)**: transacciones concurrentes no interfieren
  entre sí como si cada una viera la base de datos como si fuera la única
  ejecutándose.
- **Durabilidad**: una vez que una transacción hizo `COMMIT`, el cambio
  persiste aunque el servidor se caiga inmediatamente después.

```sql
BEGIN;
UPDATE cuentas SET saldo = saldo - 100 WHERE id = 1;
UPDATE cuentas SET saldo = saldo + 100 WHERE id = 2;
COMMIT;
```

Si el servidor falla entre las dos actualizaciones, la atomicidad garantiza
que ninguna de las dos quedó aplicada: la plata no desaparece ni se duplica.

## MVCC (Multi-Version Concurrency Control)

PostgreSQL implementa el aislamiento entre transacciones concurrentes usando
MVCC, en lugar de bloquear filas cada vez que alguien las lee. La idea de
MVCC es que, cuando una fila se actualiza, PostgreSQL no la sobreescribe en
el lugar: crea una nueva versión de la fila y mantiene la versión anterior
disponible mientras haya alguna transacción que todavía pueda necesitar
verla. Cada transacción ve una "foto" consistente de la base de datos tomada
al momento en que empezó, sin que le afecten los cambios de otras
transacciones concurrentes que todavía no hicieron `COMMIT`.

La gran ventaja de MVCC es que los lectores nunca bloquean a los escritores y
los escritores nunca bloquean a los lectores: se puede leer una tabla
mientras otra transacción la está modificando, sin esperas. La contrapartida
es que las versiones viejas de las filas (las llamadas "tuplas muertas") se
tienen que limpiar periódicamente con un proceso llamado `VACUUM`, o el
tamaño de la base crece innecesariamente.

## Índices

Un índice es una estructura de datos auxiliar (típicamente un árbol B-tree)
que PostgreSQL mantiene para poder encontrar filas rápidamente sin tener que
recorrer la tabla entera. Sin un índice sobre la columna `email`, buscar un
usuario por email implica revisar fila por fila (`sequential scan`); con un
índice, PostgreSQL puede saltar directo a la fila que corresponde.

```sql
CREATE INDEX idx_usuarios_email ON usuarios (email);
```

Los índices aceleran las lecturas pero tienen un costo: cada `INSERT` o
`UPDATE` también tiene que actualizar los índices asociados a la tabla, así
que agregar índices de más puede ralentizar las escrituras sin necesidad.

## Claves primarias y foráneas

Una clave primaria (`PRIMARY KEY`) identifica de forma única cada fila de
una tabla y PostgreSQL crea automáticamente un índice sobre ella. Una clave
foránea (`FOREIGN KEY`) es una restricción que obliga a que el valor de una
columna exista como clave primaria en otra tabla, garantizando integridad
referencial: no se puede insertar un pedido que apunte a un `usuario_id` que
no existe, y por default tampoco se puede borrar un usuario que todavía
tenga pedidos asociados (a menos que se configure `ON DELETE CASCADE` u
otra estrategia explícita).

```sql
CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    total NUMERIC(10, 2) NOT NULL
);
```

## Replicación

PostgreSQL soporta replicación: mantener una o más copias (réplicas) de la
base de datos en otros servidores, que se actualizan automáticamente a
medida que ocurren cambios en el servidor principal. Sirve para dos cosas
principales: alta disponibilidad (si el servidor principal falla, una
réplica puede promoverse y tomar su lugar) y distribuir la carga de lectura
(las consultas de solo lectura se pueden dirigir a las réplicas para no
sobrecargar al servidor principal, que es el único que acepta escrituras).

## Consultas (queries)

SQL permite combinar datos de varias tablas con `JOIN`, filtrar filas con
`WHERE`, agrupar resultados con `GROUP BY` y ordenar con `ORDER BY`. El
planificador de consultas de PostgreSQL (`query planner`) decide
automáticamente la estrategia más eficiente para ejecutar una consulta
(qué índices usar, en qué orden combinar las tablas), y el comando
`EXPLAIN ANALYZE` permite ver ese plan de ejecución para diagnosticar
consultas lentas.
