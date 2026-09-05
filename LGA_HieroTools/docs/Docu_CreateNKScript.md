# Create NK v000

Crea el comp v000 desde un template del proyecto. El aPlate es obligatorio.
El escaneo y la escritura corren en workers; los diálogos, en el hilo principal.

Si faltan secuencias EXR denoised para los plates del shot que tienen slots
en el template (a–f), aparece una sola confirmación con todos los faltantes.
El cartel destaca `Missing denoised`, los Reads afectados y `original template
paths` para identificar el problema y la consecuencia de continuar de un vistazo.
`Cancel` termina sin escribir. `Continue` permite elegir el rango y crear el
script conservando los tríos Read/Anchor/Stamp y las rutas originales de esos
denoised, incluso el nombre del shot de origen y los placeholders del template.
Los rangos de esos Reads también se conservan. El aviso final identifica cuáles
quedaron pendientes; sus rutas se deben corregir cuando estén los renders.

Los denoised encontrados se actualizan normalmente. Los slots de plates que
el shot no tiene se eliminan junto con sus denoised. Las columnas extra con
medios existentes se clonan como antes. La conservación no inventa rutas ni
renders para columnas que el template no contempla.

Si el destino existe, se solicita además autorización para sobrescribirlo y se
guarda la copia `.nk~`. Esta confirmación es independiente de los denoised.
