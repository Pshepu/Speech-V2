# Prompt de investigación para Claude in Chrome

Copia TODO lo que está debajo de la línea y pégalo en Claude in Chrome.

---

Eres un investigador experto en adquisición de segundas lenguas (SLA), diseño instruccional y productos de IA para aprender idiomas. Necesito una investigación ONLINE profunda, con fuentes verificables, para mejorar una aplicación personal de aprendizaje de idiomas. Navega por artículos científicos (Google Scholar, Cambridge Core, ResearchGate, Wiley, Taylor & Francis, ERIC, Language Learning & Technology, ReCALL, System, TESOL Quarterly, Studies in Second Language Acquisition), documentación técnica y páginas de productos. Lee los abstracts y, cuando sea posible, los resultados (tamaños de efecto). No inventes datos: si algo no está verificado, márcalo como "no verificado".

## 1. Contexto del usuario

- Hispanohablante de Chile, ingeniero en informática. Meta: llegar a un nivel **C1** (o lo más cerca posible) estudiando solo, principalmente en **inglés** y también en **portugués de Brasil** y **alemán** (y algo de francés), orientado a su carrera tech (trabajo remoto, entrevistas, reuniones, emigrar).
- Puede dedicar más o menos 20-60 minutos al día. Necesita motivación visible: quiere ver claramente que avanza.

## 2. La aplicación actual ("Speech V2")

Aplicación local (Windows) con backend FastAPI (Python) y frontend Vue. **Interfaz en español.** Funcionalidades actuales:

1. **Misiones de inmersión (rol con IA)**, inspiradas en el entrenamiento militar de idiomas (DLI): informe previo, personaje con información que hay que obtener (vacío de información), objetivos que se marcan solos, imprevistos, modo "Entrenamiento" (pistas, traducciones, autocorrección guiada con pista antes de la solución) o "Inmersión total", informe final (After Action Review) con errores, versiones más naturales y vocabulario. Campañas escritas a mano (Londres, Silicon Valley tech, Nueva York, São Paulo, Berlín, Hamburgo, París) más una "misión del día" generada por IA. Modos de conversación: libre, debate, entrevista, técnica Feynman, contar historias, actualidad, small talk. Modo manos libres por voz.
2. **Pronunciación por fonema**: modelo wav2vec2 (facebook/wav2vec2-lv-60-espeak-cv-ft) en CPU + espeak-ng + alineación forzada CTC. Puntúa cada fonema, detecta qué sonido se produjo en su lugar y da consejos para hispanohablantes. Incluye shadowing y pares mínimos con voces variadas (entrenamiento fonético de alta variabilidad, HVPT).
3. **Repaso espaciado con FSRS**: palabras (de reconocimiento a frases con hueco), expresiones (producción: español → idioma), los propios errores del usuario convertidos en tarjetas, trucos mnemotécnicos con IA y respuesta por voz.
4. **Vocabulario por frecuencia** (3.000-5.000 palabras por idioma) y paquetes C1 (phrasal verbs, colocaciones, modismos, conectores, vocabulario académico, inglés técnico para informática).
5. **Gramática**: lecciones A1-C1 con explicación en español, errores típicos de hispanohablantes y ejercicios (elegir, completar, ordenar, corregir, traducir).
6. **Escucha**: diálogos y pódcasts generados a su nivel con varias voces, preguntas, resumen corregido, dictogloss y dictado.
7. **Lectura**: textos generados o importados, palabras tocables para traducir y guardar, y resumen corregido.
8. **Fluidez**: técnica 4/3/2, lectura repetida (palabras por minuto) y repaso rápido.
9. **Evaluación de nivel MCER por destreza**: test de tamaño de vocabulario con pseudopalabras, prueba oral y prueba escrita evaluadas por IA con descriptores MCER.
10. **Plan diario** con 4 tareas esenciales y extras, racha, punto de partida comparado con el estado actual, e hitos.

## 3. Restricciones técnicas (muy importantes)

- **IA de texto: solo Groq, plan GRATUITO.** Modelos: openai/gpt-oss-120b (principal), openai/gpt-oss-20b y qwen/qwen3.8-27b. Límites por modelo: ~8.000 tokens/minuto, ~1.000 peticiones/día y **200.000 tokens/día** (ventana móvil). Qwen además: 1.000 tokens de salida por minuto.
- **Comprobado**: la caché de prompts de Groq NO se refleja en el plan gratuito (los tokens repetidos se descuentan igual). La Batch API y el modo Flex son solo de pago.
- **Problema principal**: cada turno de misión envía ~1.000-1.500 tokens (instrucciones + historial) y genera ~100-300. Una misión completa con su informe cuesta ~20.000-30.000 tokens. Con lo que consumen otras funciones, salen **unas 3 misiones al día**. Se quieren muchas más.
- Voz a texto: Whisper (Groq, límite aparte por segundos de audio). Texto a voz: edge-tts (gratis).
- Hardware: Windows, GPU GTX 1050 de **2 GB** (no sirve para LLM grandes) y CPU (modelo de fonemas en CPU).

## 4. Preguntas de investigación

### A. Cómo se llega a un nivel alto (C1) de forma eficiente
1. ¿Qué técnicas tienen MEJOR evidencia (metaanálisis, tamaños de efecto) para adultos autodidactas? Incluye como mínimo: práctica de recuperación, repetición espaciada (FSRS frente a SM-2), input comprensible / lectura y escucha extensas, narrow reading/listening, output forzado (pushed output), feedback correctivo (prompts frente a recasts, feedback escrito), enseñanza basada en tareas (TBLT: ciclo pre-tarea → tarea → foco en la lengua), repetición de tareas, planificación previa, shadowing, HVPT, colocaciones y lenguaje formulaico, vocabulario deliberado frente a incidental (cuántos encuentros hacen falta para el uso productivo), intercalado, práctica deliberada, escritura con feedback y fluidez (las 4 vertientes de Nation).
2. ¿Cuántas horas estima la investigación (FSI, DLI, Cambridge "Guided Learning Hours") para pasar de A1/B1 a C1? ¿Qué se sabe para hispanohablantes que aprenden inglés, portugués o alemán?
3. ¿Qué hacen concretamente los programas intensivos con mejores resultados (Defense Language Institute, FSI, Middlebury Language Pledge, programas de inmersión corporativa)? Horario diario, proporción input/output y tipo de tareas.
4. Métodos de autodidactas y comunidades (Refold, AJATT, método de Arguelles, Benny Lewis, Glossika, Pimsleur, LingQ, Anki sentence mining): ¿qué partes tienen respaldo científico y cuáles son humo?

### B. Diseño de misiones / rol con IA (lo más importante)
5. ¿Qué dice la investigación sobre chatbots y agentes conversacionales con LLM para la expresión oral (metaanálisis 2023-2026, por ejemplo Hou & Min 2025 en ReCALL)? ¿Qué características de diseño explican los efectos más grandes (feedback, rol, objetivos, voz frente a texto, andamiaje)?
6. ¿Cómo diseñan sus roleplays las mejores apps (Duolingo Max "Roleplay"/"Video Call", Speak, Praktika, Loora, ELSA, Talkpal, Langua, TalkAbroad, Character.ai)? Flujo, objetivos, cómo dan feedback, cómo repiten escenarios y cómo controlan el coste de la IA.
7. **Diseños que gasten POCOS tokens** sin perder valor. Por ejemplo: misiones con guion o árbol de diálogo pregenerado (sin LLM en tiempo real) donde el alumno habla y se evalúa con reconocimiento de voz; clasificar la respuesta del alumno con un modelo pequeño en lugar de generar; resúmenes del historial; prompts compactos; repartir la carga entre modelos; generar escenas sin conexión y reutilizarlas; "repetición de tarea con variación". ¿Hay papers o artículos de ingeniería sobre esto?
8. ¿Sería viable un LLM LOCAL pequeño (Ollama o llama.cpp: Qwen3 4B, Gemma 3 4B, Phi-4-mini, Llama 3.2 3B) en una PC con GTX 1050 de 2 GB más CPU para hacer de personaje en conversaciones A1-B2? Velocidad esperada (tokens/s) y calidad. ¿Qué modelo pequeño es mejor en inglés, portugués y alemán?
9. ¿Cómo integrar en las misiones el vocabulario que el alumno está aprendiendo (tarjetas que tocan hoy) para lograr los ~10-18 encuentros necesarios para el uso productivo?

### C. Motivación y medición del progreso
10. ¿Qué mecánicas de motivación funcionan a largo plazo según la investigación (rachas, metas, progreso visible, autodeterminación) y cuáles se vuelven contraproducentes?
11. ¿Cómo medir el progreso hacia C1 de forma fiable y barata (medidas CAF de complejidad, precisión y fluidez, palabras por minuto, tamaño de vocabulario, autoevaluación con "can-do statements")?

## 5. Formato de respuesta que necesito

1. **Resumen ejecutivo** (10 viñetas): lo que más impacto tendría en la app.
2. **Tabla de técnicas** con columnas: Técnica | Evidencia (tipo de estudio + tamaño de efecto si lo hay) | Fuente (enlace) | Cómo aplicarla en la app (concreto) | Coste en tokens de Groq (ninguno/bajo/medio/alto) | Prioridad (1-5).
3. **Diseño recomendado de misiones** con poco consumo de tokens: flujo paso a paso, qué parte usa LLM y cuál no, y una estimación de tokens por misión.
4. **Comparativa de apps** (punto 6): qué copiar y qué evitar.
5. **Viabilidad del LLM local** (punto 8), con números.
6. **Lista de mejoras priorizadas** para implementar (de mayor a menor impacto/esfuerzo), cada una con una descripción técnica breve para que un desarrollador la implemente.
7. **Fuentes**: lista completa de enlaces. Marca con ⚠️ lo que sea de baja calidad (blogs, marketing) o no verificado.

Responde en español. Sé crítico: prioriza metaanálisis y estudios controlados sobre opiniones, e indica cuándo la evidencia es débil o contradictoria.
