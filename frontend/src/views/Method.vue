<template>
  <div class="method">
    <div class="page-head"><div><h1>🧭 El método</h1><p>Por qué la app funciona así: cada módulo responde a algo que la investigación sobre adquisición de idiomas ha comprobado.</p></div></div>

    <div class="card">
      <h2>1. Misiones: aprender haciendo (enseñanza por tareas + inmersión)</h2>
      <p>Las escuelas militares de idiomas (como el Defense Language Institute de EE. UU.) se apoyan en la <b>inmersión</b> (aulas sin la lengua materna) y en la <b>instrucción basada en tareas</b>: usar el idioma para conseguir algo concreto, no para recitar reglas. Según el DLI, los alumnos con inmersión aprobaban más a menudo su examen final de dominio.</p>
      <p>Por eso las misiones tienen un <b>informe previo</b>, un personaje que tiene información que necesitas (<i>vacío de información</i>: te obliga a preguntar, negociar y aclarar), complicaciones inesperadas y un <b>informe posterior (AAR)</b> con tus errores. Hablar con varios personajes y acentos te prepara para conversaciones reales.</p>
    </div>

    <div class="card">
      <h2>2. Repaso espaciado con recuerdo activo (FSRS)</h2>
      <p>Intentar recordar antes de ver la respuesta (<i>efecto de testeo</i>) y espaciar los repasos son dos de las técnicas de memoria más sólidas que existen. FSRS, el algoritmo que usa Anki hoy, predice cuándo vas a olvidar cada tarjeta mejor que el antiguo SM-2 para casi todos los usuarios, y suele necesitar menos repasos para la misma retención.</p>
      <p>Tus errores de las misiones, la conversación y la escritura se convierten <b>automáticamente</b> en tarjetas: repasas justo lo que te cuesta.</p>
    </div>

    <div class="card">
      <h2>3. Vocabulario por frecuencia</h2>
      <p>Para entender bien un texto necesitas conocer alrededor del 95-98 % de sus palabras. Con unas 2.000-3.000 familias de palabras frecuentes ya se alcanza buena parte de la comprensión oral. Por eso el vocabulario está ordenado por frecuencia real de uso: las primeras palabras rinden muchísimo más.</p>
    </div>

    <div class="card">
      <h2>4. Input comprensible</h2>
      <p>Adquirimos idiomas sobre todo entendiendo mensajes un poco por encima de nuestro nivel. Las lecturas se generan a tu nivel, con audio, y puedes tocar cualquier palabra para traducirla y guardarla (<i>sentence mining</i>).</p>
    </div>

    <div class="card">
      <h2>5. Pronunciación: oído primero, luego boca</h2>
      <p>El <b>entrenamiento fonético de alta variabilidad</b> (escuchar pares mínimos como <i>ship/sheep</i> en boca de muchas voces distintas) mejora la percepción de sonidos nuevos, y esa mejora suele trasladarse a la pronunciación. Por eso “Oído” usa voces y acentos aleatorios.</p>
      <p>Al hablar, un modelo de reconocimiento de <b>fonemas</b> evalúa cada sonido que produces (no adivina la palabra como un dictado normal) y te dice qué sonido le llegó en su lugar. El <b>shadowing</b> (repetir justo detrás del nativo) tiene buena evidencia para la comprensión auditiva y es útil para el ritmo y la entonación.</p>
    </div>

    <div class="card">
      <h2>6. Fluidez: las 4 vertientes de Paul Nation</h2>
      <p>Un curso equilibrado reparte el tiempo entre <b>input</b> (leer/escuchar), <b>output</b> (hablar/escribir), <b>estudio deliberado</b> (gramática, vocabulario, pronunciación) y <b>desarrollo de la fluidez</b> con material conocido. La técnica 4/3/2 y la lectura repetida entrenan esto último: decir lo mismo cada vez más rápido.</p>
    </div>

    <div class="card">
      <h2>7. Constancia e intercalado</h2>
      <p>Sesiones cortas y diarias rinden más que maratones. El plan diario mezcla actividades distintas (intercalado) y se adapta a tus puntos débiles: sonidos con peor puntaje, tarjetas vencidas y la siguiente misión o lección.</p>
    </div>

    <div class="card">
      <h3>Fuentes</h3>
      <ul class="muted">
        <li><a href="https://www.dliflc.edu/lang_day_globe_06" target="_blank">DLIFLC: inmersión y enseñanza basada en tareas</a></li>
        <li><a href="https://cnrk.cnic.navy.mil/News/Article/3069631" target="_blank">US Navy: resultados de la inmersión en el DLI</a></li>
        <li><a href="https://docs.ankiweb.net/faqs/what-spaced-repetition-algorithm.md" target="_blank">Anki: algoritmos de repetición espaciada (FSRS)</a></li>
        <li><a href="https://resolve.cambridge.org/core/journals/studies-in-second-language-acquisition/article/high-variability-phonetic-training-hvpt-a-metaanalysis-of-l2-perceptual-training-studies/6ABB8C1F32D88D53EA8D05A4565E76F6/core-reader" target="_blank">Metaanálisis de HVPT (percepción), 2025</a></li>
        <li><a href="https://www.cambridge.org/core/product/E38D8F5CE65DC708137B0E95F97C6BC7" target="_blank">Metaanálisis: de la percepción a la producción, 2024</a></li>
        <li><a href="https://journal.uia.no/index.php/NJLTL/article/view/1139" target="_blank">Shadowing: teoría e investigación</a></li>
        <li><a href="https://www.lextutor.ca/cover/papers/schmitt_etal_2011.pdf" target="_blank">Schmitt et al. (2011): cobertura léxica y comprensión</a></li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.method .card h2 { font-size: 1.1rem; }
</style>
