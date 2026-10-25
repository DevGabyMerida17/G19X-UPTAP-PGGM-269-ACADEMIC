// Mismas reglas que backend/app/validaciones.py, para avisar antes de enviar.

const CORREO = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;
const PARTICULAS = new Set(["de", "del", "la", "las", "los", "y", "e", "van", "von", "da", "di", "do", "dos", "das"]);
const PALABRA = /^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+$/;
const VOCAL = /[aeiouáéíóúü]/;

/** Devuelve el mensaje de error, o "" si el correo es válido. */
export function errorCorreo(v) {
  if (/\s/.test(v)) return "El correo no puede tener espacios.";
  if (!v) return "Escribe tu correo.";
  if (!CORREO.test(v)) return "Escribe un correo válido, por ejemplo nombre@empresa.com.";
  return "";
}

/** Devuelve el mensaje de error, o "" si el nombre es válido. */
export function errorNombre(v) {
  if (!v) return "Escribe el nombre completo.";
  if (v !== v.trim()) return "El nombre no puede empezar ni terminar con espacios.";
  if (v.includes("  ")) return "Usa un solo espacio entre cada palabra del nombre.";
  if (/\d/.test(v)) return "El nombre no puede tener números.";
  const palabras = v.split(" ");
  if (palabras.some((p) => !PALABRA.test(p))) return "El nombre solo puede tener letras (se permiten acentos y ñ).";
  const principales = palabras.filter((p) => !PARTICULAS.has(p.toLowerCase()));
  if (principales.length < 2) return "Escribe el nombre completo: al menos un nombre y un apellido.";
  for (const p of principales) {
    const bajo = p.toLowerCase();
    if (bajo.length < 2) return "Cada nombre y apellido debe tener al menos 2 letras.";
    if (!VOCAL.test(bajo)) return `"${p}" no parece un nombre real.`;
    if (/(.)\1\1/.test(bajo) || new Set(bajo).size === 1) return `"${p}" no parece un nombre real (tiene letras repetidas).`;
  }
  return "";
}

/* Aviso flotante con el estilo de la plataforma (en lugar del globo gris del navegador).
   Se dibuja fuera de React, pegado debajo del campo, y desaparece solo. */
const ICONO_ALERTA = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/></svg>';
let globo = null;
let temporizador = null;

function quitarGlobo() {
  clearTimeout(temporizador);
  if (globo) {
    const g = globo;
    globo = null;
    g.classList.remove("visible");
    setTimeout(() => g.remove(), 180);
  }
  window.removeEventListener("scroll", quitarGlobo, true);
  window.removeEventListener("resize", quitarGlobo);
}

function avisar(input, mensaje) {
  if (globo && globo.dataset.para === input.name && globo.textContent === mensaje) {
    // Mismo aviso repetido: solo se reinicia el tiempo y se sacude un poco.
    clearTimeout(temporizador);
    globo.classList.remove("sacudir"); void globo.offsetWidth; globo.classList.add("sacudir");
  } else {
    quitarGlobo();
    globo = document.createElement("div");
    globo.className = "globo-aviso";
    globo.setAttribute("role", "alert");
    globo.dataset.para = input.name;
    globo.innerHTML = `${ICONO_ALERTA}<span></span>`;
    globo.querySelector("span").textContent = mensaje;
    document.body.appendChild(globo);
    const r = input.getBoundingClientRect();
    globo.style.top = `${r.bottom + window.scrollY + 10}px`;
    globo.style.left = `${r.left + window.scrollX}px`;
    globo.style.maxWidth = `${Math.max(220, Math.min(r.width, window.innerWidth - r.left - 16))}px`;
    requestAnimationFrame(() => globo && globo.classList.add("visible"));
    window.addEventListener("scroll", quitarGlobo, true);
    window.addEventListener("resize", quitarGlobo);
    input.addEventListener("blur", quitarGlobo, { once: true });
  }
  temporizador = setTimeout(quitarGlobo, 3000);
}

/** Props para campos de correo: no deja escribir ni pegar espacios. */
export const propsCorreo = {
  onKeyDown(e) {
    if (e.key === " ") { e.preventDefault(); avisar(e.target, "El correo no puede tener espacios."); }
  },
  onInput(e) {
    if (/\s/.test(e.target.value)) {
      e.target.value = e.target.value.replace(/\s+/g, "");
      avisar(e.target, "El correo no puede tener espacios.");
    }
  },
};

/** Props para campos de contraseña: la tecla espacio simplemente no escribe nada (sin aviso). */
export const propsPassword = {
  onKeyDown(e) {
    if (e.key === " ") e.preventDefault();
  },
  onInput(e) {
    if (/\s/.test(e.target.value)) e.target.value = e.target.value.replace(/\s+/g, "");
  },
};

/** Props para campos de nombre: no deja escribir ni pegar números. */
export const propsNombre = {
  onKeyDown(e) {
    if (/^\d$/.test(e.key)) { e.preventDefault(); avisar(e.target, "El nombre solo puede tener letras."); }
  },
  onInput(e) {
    if (/\d/.test(e.target.value)) {
      e.target.value = e.target.value.replace(/\d+/g, "");
      avisar(e.target, "El nombre solo puede tener letras.");
    }
  },
};

/** Primer nombre solo si es un nombre real; si quedó registrado con números, devuelve "". */
export function nombreDePila(nombre = "") {
  return errorNombre(nombre.trim()) ? "" : nombre.trim().split(" ")[0];
}

/** Nombre para mostrar: el nombre real o "Sin nombre registrado" (nunca un número). */
export function nombreVisible(nombre = "") {
  return errorNombre(nombre.trim()) ? "Sin nombre registrado" : nombre.trim();
}
