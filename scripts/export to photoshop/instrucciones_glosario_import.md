# Instrucciones: generar glosario_TomoXX_import.json a partir de imgtrans_TomoXX.json

Estas instrucciones son autocontenidas. Súbelas junto con el fichero
`imgtrans_TomoXX.json` del tomo que quieras procesar (cámbiale el nombre
al tomo real, ej. `imgtrans_Tomo14.json`) y pide:

> "Sigue estas instrucciones para generar el glosario_TomoXX_import.json de este tomo."

---

## 1. Estructura de entrada (imgtrans_TomoXX.json)

Es un JSON con esta forma:

```json
{
  "directory": "...",
  "pages": {
    "TomoXX-03.jpg": [ { ...bloque de texto... }, { ... } ],
    "TomoXX-04.jpg": [ ... ],
    ...
  }
}
```

- `pages` es un diccionario ordenado: cada clave es el nombre de la página de imagen.
- El **número de página de archivo** se extrae del nombre de archivo (ej. `TomoXX-05.jpg`
  → `"05"`). Este número **no es necesariamente el que hay que escribir en `pagina`**,
  ver el punto 1bis sobre el desfase de páginas.
- Cada página contiene una **lista de bloques de texto** (globos). El **número de globo**
  es la posición del bloque dentro de esa lista, empezando en 1 (`01`, `02`, `03`...).
  Este orden ya es el orden de lectura correcto (coincide con `sort_regions`). El globo
  **no lleva desfase**, solo la página.
- El texto traducido de cada bloque está en el campo `"translation"` de cada bloque.

## 1bis. Desfase de páginas (pagina_offset)

El número de página del nombre de archivo no siempre coincide con la numeración "real"
del tomo (portada, contraportada, prólogo del autor, etc. pueden desplazarlo). Antes de
generar el fichero:

1. Pregunta al usuario (si no lo ha dicho ya): *"¿Cuál es el desfase de páginas de este
   tomo? (cuántas páginas hay que sumar al número de archivo para llegar a la página
   real)"*. Ha sido +3 en el Tomo11 y +2 en el Tomo13 — **no asumas que es el mismo
   valor entre tomos**, cada uno puede tener un número distinto de páginas de portada.
2. El valor de `pagina` en la salida siempre es `número_de_archivo + pagina_offset`,
   formateado a 2 dígitos (`f'{n:02d}'`).
3. El campo `globo` nunca lleva desfase.
4. Indica en tu respuesta al usuario qué `pagina_offset` has aplicado, para que lo pueda
   confirmar o corregir.

## 1ter. Páginas que no forman parte de la historia

Las primeras páginas de un tomo suelen ser prólogo/dedicatoria del autor real (pueden
mencionar nombres de personas reales: guionista, dibujante, colorista, editor...). Esas
páginas **no se analizan** para el glosario — no son personajes de ficción. Identifícalas
por el contexto (agradecimientos, biografía del autor, dedicatorias) antes de empezar a
extraer nombres, y empieza el análisis narrativo a partir de donde arranca la historia.

## 2. Estructura de salida (glosario_TomoXX_import.json)

```json
{
  "tomo": "TomoXX",
  "entradas": [
    {
      "nombre": "Nombre propio",
      "tipo": "Personaje | Paraje | Elemento | Error | Otro",
      "tomo": "TomoXX",
      "pagina": "05",
      "globo": "02",
      "nota": "Primera aparición / Fallece / Se transforma / etc.",
      "apariciones": ["05|02", "06|01", "12|09", "..."]
    }
  ]
}
```

`apariciones` es la lista **completa** de página|globo donde ese nombre aparece
literalmente en el tomo (con el desfase de páginas ya aplicado). Es un campo aparte de
`pagina`/`globo` (que marcan el evento narrativo concreto de esa entrada) — ver punto 4bis
sobre cómo calcularlo. Es opcional solo para la entrada tipo "Error", donde no aplica.

Tipos válidos:
- **Personaje**: persona, criatura, ente con nombre propio.
- **Paraje**: lugar, territorio, edificio con nombre propio.
- **Elemento**: objeto, orden/facción, concepto con nombre propio que no encaja en los anteriores.
- **Error**: no es una categoría narrativa — se usa para señalar una **inconsistencia de
  traducción** (mismo nombre escrito de forma distinta en el tomo, nombre mal traducido...)
  o cualquier **corrupción de datos** que encuentres en el propio `imgtrans_TomoXX.json`
  (por ejemplo, texto de interfaz pegado por error dentro de una traducción). La nota debe
  explicar el problema con precisión, no un evento de la trama.
- **Otro**: cuando ninguno de los anteriores encaja.

## 3. Criterio de qué anotar

**No** se anota cada mención de cada nombre propio (serían cientos de líneas por tomo,
demasiado ruido). Se anotan solo **momentos narrativos con valor de consulta**:

- Primera aparición de cada personaje/paraje/elemento relevante.
- Revelaciones de parentesco o identidad ("se revela que es hijo/madre/hermano de...").
- Muertes.
- Resurrecciones / transformaciones / cambios de bando.
- Ascensos o pérdidas de poder/trono relevantes para seguir la trama.
- Cualquier inconsistencia de traducción detectada (tipo "Error").

Un mismo nombre puede tener **varias entradas** a lo largo del tomo (una por cada
evento relevante), igual que en el ejemplo de arriba.

No hace falta preguntar antes de aplicar este criterio: procede directamente y, si el
usuario quiere un nivel de detalle distinto (por ejemplo, exhaustivo), lo pedirá.

Este criterio "solo eventos relevantes" aplica a las **notas curadas**. El registro
exhaustivo de dónde aparece cada nombre no depende de este criterio ni de tu lectura:
se cubre aparte con el campo `apariciones` (ver punto 4bis), calculado por búsqueda de
texto, no por selección manual.

## 4. Regla de verificación (obligatoria antes de entregar el archivo)

Para cada entrada, el `nombre` (o al menos su palabra significativa principal) debe
aparecer **literalmente** en el texto (`translation`) del bloque señalado por
`pagina`/`globo`. Antes de entregar el fichero final:

1. Recorre todas las entradas generadas.
2. Para cada una, comprueba que el nombre aparece en el texto de ese globo exacto.
3. Si no aparece (por ejemplo, porque el evento se narra en un globo cercano sin
   nombrar al personaje):
   - Si hay un globo cercano donde sí se le nombra y sigue siendo coherente con la
     nota, mueve la entrada a ese globo.
   - Si no existe tal globo (ej. narración en primera persona sin nombrar al
     hablante), deja la entrada donde mejor describe el evento pero indícalo
     explícitamente en la nota, por ejemplo:
     `"(no se le nombra en este globo; se infiere por contexto) ..."`.

No entregues el fichero sin haber hecho esta comprobación.

## 4bis. Cálculo de `apariciones` (obligatorio, por script — no a mano)

Este es un paso mecánico de búsqueda de texto, no de criterio narrativo, así que no se
salta nunca y no admite selección manual (el motivo: seleccionar a mano qué apariciones
mostrar es exactamente el error que motivó añadir este campo — se pueden pasar por alto
menciones sin darse cuenta).

1. Para cada **nombre único** del glosario (agrupa todas sus entradas por `nombre`),
   define una o varias claves de búsqueda literales — normalmente el propio nombre, o
   su palabra distintiva si el nombre completo incluye artículos ("Lord Heron" → busca
   "Heron"; "El Niddhog" → busca "Niddhog"). Si dos entidades distintas comparten una
   palabra (p. ej. "Flamina" aparece tanto en un personaje como en el nombre de una
   orden), usa una clave más específica (la frase completa) para evitar mezclarlas.
2. Recorre **todos** los bloques de **todas** las páginas del tomo y comprueba si el
   texto de `translation` contiene esa clave (comparación insensible a mayúsculas).
3. Por cada coincidencia, añade `"pagina|globo"` a la lista `apariciones` de esa entrada
   (con el `pagina_offset` del punto 1bis ya aplicado, el `globo` tal cual).
4. Las variantes de una inconsistencia (entrada tipo "Error") pueden buscar varias claves
   a la vez (todas las grafías detectadas), para reflejar el recuento combinado.
5. Todas las entradas que compartan el mismo `nombre` llevan la misma lista de
   `apariciones` (no hace falta recalcularla por evento, solo por nombre).

Hazlo con un script (no leyendo el tomo de nuevo a mano) para que el resultado sea
determinista y completo.

## 5. Inconsistencias de traducción

Si detectas que un mismo nombre propio aparece escrito de dos formas distintas en el
tomo (variantes, erratas, mayúsculas/minúsculas inconsistentes...), añade una entrada
de tipo `"Error"` señalándolo, con recuento de apariciones de cada variante si es
sencillo de calcular. No corrijas la traducción original tú mismo: solo señálalo.

## 6. Entrega

Genera el archivo `glosario_TomoXX_import.json` (con el número de tomo real) como
fichero descargable, validando que es JSON correcto antes de entregarlo. En tu mensaje
de entrega indica también:

- el `pagina_offset` que has aplicado (punto 1bis), para que el usuario lo confirme,
- si has excluido páginas de prólogo/dedicatoria (punto 1ter),
- si has encontrado alguna corrupción de datos o inconsistencia de traducción (tipo "Error").
