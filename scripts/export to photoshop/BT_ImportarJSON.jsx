/*******************************************************************************
 * BT_ImportarJSON.jsx  —  NavajaCRG / BallonsTranslator 
 * Versión 5.1
 *
 *  A) INSERTAR CAPAS DE TEXTO en la página activa
 *     TextLayer por globo con formato NavajaCRG + delimitadores Markdown.
 *     Busca automáticamente el JSON en la carpeta del documento.
 *
 *  B) INSERTAR CAPAS DE TEXTO + PLANCHA INPAINTED
 *     Igual que A pero además importa la imagen inpainted (cualquier extensión)
 *     cuyo nombre coincida con el de la página activa, colocándola justo
 *     encima de la capa de fondo/plancha.
 *
 *  C) SIN DOCUMENTO ABIERTO — IMPORTACIÓN POR LOTES
 *     Si no hay ningún documento abierto en Photoshop, se pide el JSON de
 *     BallonsTranslator directamente y se muestra un panel de selección
 *     múltiple de páginas (al estilo del BallonTranslator_PS_Bridge.jsx
 *     oficial, pero en español y usando el motor propio de NavajaCRG:
 *     plantilla de fuente + delimitadores PS, no formato nativo de PS).
 *     Por cada página seleccionada se abre la imagen original como
 *     documento nuevo, se insertan las capas de texto y, si se marca la
 *     opción, se importa también la plancha inpainted correspondiente.
 ******************************************************************************/

#target photoshop

// ---------------------------------------------------------------------------
// UTILIDADES
// ---------------------------------------------------------------------------

function trim(s) {
    s = String(s);
    while (s.length && (s[0]===" "||s[0]==="\t"||s[0]==="\r"||s[0]==="\n")) s=s.slice(1);
    while (s.length) { var c=s[s.length-1]; if(c===" "||c==="\t"||c==="\r"||c==="\n") s=s.slice(0,-1); else break; }
    return s;
}

function padNum(n, d) {
    var s = String(parseInt(n,10)||0);
    while (s.length < d) s = "0" + s;
    return s;
}

function numPagDesdNombre(nombre) {
    var sinExt = nombre.replace(/\.[^.]+$/, "");
    var m = sinExt.match(/(\d+)$/);
    return m ? padNum(parseInt(m[1],10), 2) : null;
}

function unirLineas(raw) {
    if (!raw) return "";
    if (raw instanceof Array) raw = raw.join(" ");
    return trim(String(raw).replace(/\r/g,"").replace(/\n/g," ").replace(/\s{2,}/g," "));
}

function aOracion(texto) {
    texto = unirLineas(texto);
    if (!texto.length) return texto;
    var pre="", i=0;
    while (i<texto.length && "¡¿…—-·.".indexOf(texto[i])>=0){pre+=texto[i];i++;}
    var cuerpo=texto.slice(i);
    if (!cuerpo.length) return texto;
    var min=cuerpo.toLowerCase();
    return pre+min.charAt(0).toUpperCase()+min.slice(1);
}

// ---------------------------------------------------------------------------
// ARCHIVOS
// ---------------------------------------------------------------------------

function leerJsonBT(ruta) {
    var f=new File(ruta); if(!f.exists) throw new Error("No encontrado:\n"+ruta);
    f.encoding="UTF-8"; f.open("r"); var txt=f.read(); f.close();
    return eval("("+txt+")");
}

// Busca automáticamente el primer imgtrans_*.json en la carpeta dada
function buscarJsonEnCarpeta(rutaCarpeta) {
    var carpeta = new Folder(rutaCarpeta);
    var archivos = carpeta.getFiles("imgtrans_*.json");
    if (archivos && archivos.length > 0) return archivos[0];
    // También buscar cualquier JSON si no hay con ese prefijo
    archivos = carpeta.getFiles("*.json");
    if (archivos && archivos.length > 0) return archivos[0];
    return null;
}

// ---------------------------------------------------------------------------
// ORDENAR BLOQUES
// ---------------------------------------------------------------------------

function ordenar(bloques) {
    // Devuelve los bloques en el MISMO ORDEN que tiene BT en el JSON.
    // ESE orden es el que se refleja en Tradu.txt (línea 1 = globo 1, etc.)
    // y el que usa RellenaGlobos3.jsx para nombrar capas T-XX-01, T-XX-02...
    // NO reordenamos por coordenadas: BT puede haber ordenado diferente.
    var c = [];
    for (var i = 0; i < bloques.length; i++) c.push(bloques[i]);
    return c;
}

// ---------------------------------------------------------------------------
// COLORES Y FORMATO
// ---------------------------------------------------------------------------

function crearColor(r,g,b){var c=new SolidColor();c.rgb.red=r;c.rgb.green=g;c.rgb.blue=b;return c;}

function justifPS(str) {
    if (!str) return Justification.CENTER;
    str = String(str).toLowerCase();
    if (str==="left"  ||str==="izquierda") return Justification.LEFT;
    if (str==="right" ||str==="derecha")   return Justification.RIGHT;
    if (str==="justifyfull"||str==="justificado") return Justification.FULLJUSTIFY;
    return Justification.CENTER;
}

function antiAliasPS(str) {
    if (!str) return AntiAlias.STRONG;
    str = String(str).toUpperCase();
    if (str==="NONE")   return AntiAlias.NONE;
    if (str==="SHARP")  return AntiAlias.SHARP;
    if (str==="CRISP")  return AntiAlias.CRISP;
    if (str==="SMOOTH") return AntiAlias.SMOOTH;
    return AntiAlias.STRONG;
}

function antiAliasPSId(str) {
    if (!str) return "antiAliasStrong";
    var m = {"NONE":"antiAliasNone","SHARP":"antiAliasSharp","CRISP":"antiAliasCrisp",
             "SMOOTH":"antiAliasSmooth","STRONG":"antiAliasStrong"};
    return m[String(str).toUpperCase()] || "antiAliasStrong";
}

// ---------------------------------------------------------------------------
// LEER PLANTILLA ACTIVA DE NavajaCRG
// ---------------------------------------------------------------------------

function cargarPlantillaCRG() {
    try {
        var d = app.getCustomOptions("plantillaActiva");
        var p = {};
        try { p.nombre       = d.getString(stringIDToTypeID("fuente_nombre"));            } catch(e){ p.nombre="Arial"; }
        try { p.familia      = d.getString(stringIDToTypeID("fuente_familia"));           } catch(e){ p.familia="Arial"; }
        try { p.estiloReg    = d.getString(stringIDToTypeID("fuente_estiloRegular"));     } catch(e){ p.estiloReg="Regular"; }
        try { p.tamano       = d.getDouble(stringIDToTypeID("fuente_tamano"));            } catch(e){ p.tamano=0; }
        try { p.interlineado = d.getDouble(stringIDToTypeID("fuente_interlineado"));      } catch(e){ p.interlineado=0; }
        try { p.autoInterlin = d.getBoolean(stringIDToTypeID("fuente_autoInterlineado")); } catch(e){ p.autoInterlin=true; }
        try { p.tracking     = d.getInteger(stringIDToTypeID("fuente_tracking"));         } catch(e){ p.tracking=0; }
        try { p.escalaH      = d.getDouble(stringIDToTypeID("fuente_escalaH"));           } catch(e){ p.escalaH=100; }
        try { p.escalaV      = d.getDouble(stringIDToTypeID("fuente_escalaV"));           } catch(e){ p.escalaV=100; }
        try { p.antiAlias    = d.getString(stringIDToTypeID("fuente_antiAlias"));         } catch(e){ p.antiAlias="STRONG"; }
        try { p.justif       = d.getString(stringIDToTypeID("fuente_justif"));            } catch(e){ p.justif="CENTER"; }
        try { p.colorR       = d.getDouble(stringIDToTypeID("color_r"));                  } catch(e){ p.colorR=0; }
        try { p.colorG       = d.getDouble(stringIDToTypeID("color_g"));                  } catch(e){ p.colorG=0; }
        try { p.colorB       = d.getDouble(stringIDToTypeID("color_b"));                  } catch(e){ p.colorB=0; }
        try { p.todoMayusc   = d.getBoolean(stringIDToTypeID("todo_mayusculas_plantilla"));} catch(e){ p.todoMayusc=false; }

        // Leer delimitadores
        p.delimitadores = [];
        try {
            var numDelim = d.getInteger(stringIDToTypeID("num_delimitadores"));
            for (var i=0; i<numDelim; i++) {
                var pfx = "delim_"+i+"_";
                var del = {
                    id:"", nombre:"", delimitador:"", estilo:"", estiloNormal:"",
                    activado:false, usarFaux:false, fauxBold:false, fauxItalic:false,
                    aplicarSubrayado:false, aplicarTachado:false,
                    aplicarSuperindice:false, aplicarSubindice:false
                };
                try { del.id         = d.getString(stringIDToTypeID(pfx+"id"));          } catch(e){}
                try { del.nombre     = d.getString(stringIDToTypeID(pfx+"nombre"));      } catch(e){}
                try { del.delimitador= d.getString(stringIDToTypeID(pfx+"delimitador")); } catch(e){}
                try { del.estilo     = d.getString(stringIDToTypeID(pfx+"estilo"));      } catch(e){}
                try { del.estiloNormal=d.getString(stringIDToTypeID(pfx+"normal"));      } catch(e){}
                try { del.activado   = d.getBoolean(stringIDToTypeID(pfx+"activado"));   } catch(e){}
                try { del.usarFaux   = d.getBoolean(stringIDToTypeID(pfx+"usarFaux"));   } catch(e){}
                try { del.fauxBold   = d.getBoolean(stringIDToTypeID(pfx+"fauxBold"));   } catch(e){}
                try { del.fauxItalic = d.getBoolean(stringIDToTypeID(pfx+"fauxItalic")); } catch(e){}
                try { del.aplicarSubrayado   = d.getBoolean(stringIDToTypeID(pfx+"subrayado"));   } catch(e){}
                try { del.aplicarTachado     = d.getBoolean(stringIDToTypeID(pfx+"tachado"));     } catch(e){}
                try { del.aplicarSuperindice = d.getBoolean(stringIDToTypeID(pfx+"superindice")); } catch(e){}
                try { del.aplicarSubindice   = d.getBoolean(stringIDToTypeID(pfx+"subindice"));   } catch(e){}
                if (del.activado) p.delimitadores.push(del);
            }
        } catch(e){}

        return p;
    } catch(e) { return null; }
}

// ---------------------------------------------------------------------------
// PROCESAMIENTO DE DELIMITADORES MARKDOWN  (portado de RellenaGlobos3.jsx)
// ---------------------------------------------------------------------------

function procesarFormatoMarkdown(texto, delimitadores) {
    if (!delimitadores || delimitadores.length === 0) {
        return { texto: texto, formatos: [] };
    }

    // Ordenar: más largos primero; bold/italic antes de otros
    var delimsOrd = [];
    for (var i=0; i<delimitadores.length; i++) delimsOrd.push(delimitadores[i]);
    delimsOrd.sort(function(a,b){
        var d = b.delimitador.length - a.delimitador.length;
        if (d!==0) return d;
        var eA = a.fauxBold||a.fauxItalic, eB = b.fauxBold||b.fauxItalic;
        if (eA&&!eB) return -1; if (!eA&&eB) return 1; return 0;
    });

    var chars = [];
    for (var i=0; i<texto.length; i++) chars.push({c:texto.charAt(i), marcado:false, formatos:[]});

    for (var d=0; d<delimsOrd.length; d++) {
        var delim = delimsOrd[d];
        var dl = delim.delimitador;
        var i = 0;
        while (i < chars.length) {
            // Buscar apertura
            var ok = true;
            for (var j=0; j<dl.length; j++) {
                if (i+j>=chars.length || chars[i+j].c!==dl.charAt(j) || chars[i+j].marcado) { ok=false; break; }
            }
            if (ok) {
                // Buscar cierre
                var cierre = -1;
                for (var k=i+dl.length; k<=chars.length-dl.length; k++) {
                    var ok2=true;
                    for (var j=0; j<dl.length; j++) {
                        if (chars[k+j].c!==dl.charAt(j) || chars[k+j].marcado) { ok2=false; break; }
                    }
                    if (ok2) { cierre=k; break; }
                }
                if (cierre!==-1) {
                    for (var j=0; j<dl.length; j++) { chars[i+j].marcado=true; chars[cierre+j].marcado=true; }
                    for (var j=i+dl.length; j<cierre; j++) { if (!chars[j].marcado) chars[j].formatos.push(delim); }
                    i = cierre+dl.length;
                } else { i++; }
            } else { i++; }
        }
    }

    var textoLimpio = "";
    var formatos = [];
    for (var i=0; i<chars.length; i++) {
        if (chars[i].marcado) continue;
        textoLimpio += chars[i].c;
        var pos = textoLimpio.length-1;
        for (var f=0; f<chars[i].formatos.length; f++) {
            var dl2 = chars[i].formatos[f];
            var found = false;
            for (var g=0; g<formatos.length; g++) {
                if (formatos[g].delim===dl2 && formatos[g].fin===pos) { formatos[g].fin=pos+1; found=true; break; }
            }
            if (!found) formatos.push({inicio:pos, fin:pos+1, delim:dl2});
        }
    }

    // Fusionar contiguos
    for (var i=0; i<formatos.length; i++) {
        for (var j=i+1; j<formatos.length; j++) {
            if (formatos[i].delim===formatos[j].delim && formatos[i].fin===formatos[j].inicio) {
                formatos[i].fin=formatos[j].fin; formatos.splice(j,1); j--;
            }
        }
    }

    return { texto: textoLimpio, formatos: formatos };
}

// ---------------------------------------------------------------------------
// APLICAR FORMATO BASE A RANGO (estilo completo vía ActionDescriptor)
// ---------------------------------------------------------------------------

function aplicarFormatoBase(pf, desde, hasta) {
    try {
        var idsetd = app.charIDToTypeID("setd");
        var act = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putEnumerated(app.charIDToTypeID("TxLr"),app.charIDToTypeID("Ordn"),app.charIDToTypeID("Trgt"));
        act.putReference(app.charIDToTypeID("null"), ref);
        var idT = app.charIDToTypeID("T   ");
        var tAct = new ActionDescriptor();
        var aList = new ActionList();
        var tRange = new ActionDescriptor();
        tRange.putInteger(app.charIDToTypeID("From"), desde);
        tRange.putInteger(idT, hasta);
        var fmt = new ActionDescriptor();
        fmt.putString(app.charIDToTypeID("FntN"), pf.familia);
        fmt.putString(app.charIDToTypeID("FntS"), pf.estiloReg);
        fmt.putUnitDouble(app.charIDToTypeID("Sz  "), app.charIDToTypeID("#Pnt"), pf.tamano);
        fmt.putBoolean(app.stringIDToTypeID("autoLeading"), pf.autoInterlin);
        if (!pf.autoInterlin && pf.interlineado>0)
            fmt.putUnitDouble(app.charIDToTypeID("Ldng"), app.charIDToTypeID("#Pnt"), pf.interlineado);
        fmt.putInteger(app.charIDToTypeID("Trck"), pf.tracking||0);
        fmt.putDouble(app.stringIDToTypeID("horizontalScale"), pf.escalaH||100);
        fmt.putDouble(app.stringIDToTypeID("verticalScale"),   pf.escalaV||100);
        fmt.putEnumerated(app.stringIDToTypeID("fontCaps"), app.stringIDToTypeID("fontCaps"),
            pf.todoMayusc ? app.stringIDToTypeID("allCaps") : app.charIDToTypeID("Nrml"));
        var clr = new ActionDescriptor();
        clr.putDouble(app.charIDToTypeID("Rd  "), pf.colorR||0);
        clr.putDouble(app.charIDToTypeID("Grn "), pf.colorG||0);
        clr.putDouble(app.charIDToTypeID("Bl  "), pf.colorB||0);
        fmt.putObject(app.charIDToTypeID("Clr "), app.charIDToTypeID("RGBC"), clr);
        tRange.putObject(app.charIDToTypeID("TxtS"), app.charIDToTypeID("TxtS"), fmt);
        aList.putObject(app.charIDToTypeID("Txtt"), tRange);
        tAct.putList(app.charIDToTypeID("Txtt"), aList);
        act.putObject(idT, app.charIDToTypeID("TxLr"), tAct);
        app.executeAction(idsetd, act, DialogModes.NO);
    } catch(e) {}
}

// ---------------------------------------------------------------------------
// APLICAR ESTILO (Bold/Italic/decoración) A UN RANGO
// Portado de RellenaGlobos3.jsx → aplicarEstiloTexto / aplicarDecoracion
// ---------------------------------------------------------------------------

function aplicarEstiloRango(pf, inicio, fin, delims) {
    try {
        var idsetd = app.charIDToTypeID("setd");
        var act = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putEnumerated(app.charIDToTypeID("TxLr"),app.charIDToTypeID("Ordn"),app.charIDToTypeID("Trgt"));
        act.putReference(app.charIDToTypeID("null"), ref);
        var idT = app.charIDToTypeID("T   ");
        var tAct = new ActionDescriptor();
        var aList = new ActionList();
        var tRange = new ActionDescriptor();
        tRange.putInteger(app.charIDToTypeID("From"), inicio);
        tRange.putInteger(idT, fin);
        var fmt = new ActionDescriptor();

        // Base
        fmt.putBoolean(app.stringIDToTypeID("autoLeading"), pf.autoInterlin);
        if (!pf.autoInterlin && pf.interlineado>0)
            fmt.putUnitDouble(app.charIDToTypeID("Ldng"), app.charIDToTypeID("#Pnt"), pf.interlineado);
        fmt.putInteger(app.charIDToTypeID("Trck"), pf.tracking||0);
        fmt.putUnitDouble(app.charIDToTypeID("Sz  "), app.charIDToTypeID("#Pnt"), pf.tamano);
        fmt.putDouble(app.stringIDToTypeID("horizontalScale"), pf.escalaH||100);
        fmt.putDouble(app.stringIDToTypeID("verticalScale"),   pf.escalaV||100);
        fmt.putEnumerated(app.stringIDToTypeID("fontCaps"), app.stringIDToTypeID("fontCaps"),
            pf.todoMayusc ? app.stringIDToTypeID("allCaps") : app.charIDToTypeID("Nrml"));
        var clr = new ActionDescriptor();
        clr.putDouble(app.charIDToTypeID("Rd  "), pf.colorR||0);
        clr.putDouble(app.charIDToTypeID("Grn "), pf.colorG||0);
        clr.putDouble(app.charIDToTypeID("Bl  "), pf.colorB||0);
        fmt.putObject(app.charIDToTypeID("Clr "), app.charIDToTypeID("RGBC"), clr);

        // Separar por tipo
        var delimsEstilo=[], delimsDeco=[], delimsDespl=[];
        for (var i=0; i<delims.length; i++) {
            var d=delims[i];
            if (d.aplicarSuperindice||d.aplicarSubindice) delimsDespl.push(d);
            else if (d.aplicarSubrayado||d.aplicarTachado) delimsDeco.push(d);
            else delimsEstilo.push(d);
        }

        // Determinar estilo de fuente
        var estiloReal="", usarFaux=false, fBold=false, fItalic=false;
        for (var i=0; i<delimsEstilo.length; i++) {
            var d=delimsEstilo[i];
            if (!d.usarFaux && d.estilo && d.estilo!==pf.estiloReg) { estiloReal=d.estilo; break; }
        }
        if (!estiloReal) {
            for (var i=0; i<delimsEstilo.length; i++) {
                if (delimsEstilo[i].fauxBold)   fBold=true;
                if (delimsEstilo[i].fauxItalic) fItalic=true;
            }
        }
        // Decoración
        var subray=false, tacha=false;
        for (var i=0; i<delimsDeco.length; i++) {
            if (delimsDeco[i].aplicarSubrayado) subray=true;
            if (delimsDeco[i].aplicarTachado)   tacha=true;
        }
        // Desplazamiento
        var supInd=false, subInd=false;
        for (var i=0; i<delimsDespl.length; i++) {
            if (delimsDespl[i].aplicarSuperindice) supInd=true;
            if (delimsDespl[i].aplicarSubindice)   subInd=true;
        }

        if (estiloReal) {
            fmt.putString(app.charIDToTypeID("FntN"), pf.familia);
            fmt.putString(app.charIDToTypeID("FntS"), estiloReal);
        } else {
            fmt.putString(app.charIDToTypeID("FntN"), pf.familia);
            fmt.putString(app.charIDToTypeID("FntS"), pf.estiloReg);
            if (fBold)   fmt.putBoolean(app.stringIDToTypeID("syntheticBold"),   true);
            if (fItalic) fmt.putBoolean(app.stringIDToTypeID("syntheticItalic"), true);
        }
        if (subray) fmt.putBoolean(app.stringIDToTypeID("underline"), true);
        if (tacha)  fmt.putBoolean(app.charIDToTypeID("Stkt"),        true);

        if (supInd || subInd) {
            var ss = supInd ? 0.33 : -0.33;
            fmt.putUnitDouble(app.stringIDToTypeID("baselineShift"), app.charIDToTypeID("#Pnt"), pf.tamano*ss);
            fmt.putUnitDouble(app.charIDToTypeID("Sz  "), app.charIDToTypeID("#Pnt"), pf.tamano*0.58);
        }

        tRange.putObject(app.charIDToTypeID("TxtS"), app.charIDToTypeID("TxtS"), fmt);
        aList.putObject(app.charIDToTypeID("Txtt"), tRange);
        tAct.putList(app.charIDToTypeID("Txtt"), aList);
        act.putObject(idT, app.charIDToTypeID("TxLr"), tAct);
        app.executeAction(idsetd, act, DialogModes.NO);
    } catch(e) {}
}

function aplicarAntiAliasACapaActual(str) {
    try {
        var aaId = antiAliasPSId(str);
        var idsetd = app.charIDToTypeID("setd");
        var act = new ActionDescriptor();
        var ref = new ActionReference();
        ref.putEnumerated(app.charIDToTypeID("TxLr"),app.charIDToTypeID("Ordn"),app.charIDToTypeID("Trgt"));
        act.putReference(app.charIDToTypeID("null"), ref);
        var idT = app.charIDToTypeID("T   ");
        var tAct = new ActionDescriptor();
        tAct.putEnumerated(app.stringIDToTypeID("antiAlias"),app.stringIDToTypeID("antiAliasType"),app.stringIDToTypeID(aaId));
        act.putObject(idT, app.charIDToTypeID("TxLr"), tAct);
        app.executeAction(idsetd, act, DialogModes.NO);
    } catch(e) {}
}

// ---------------------------------------------------------------------------
// CENTRADO VERTICAL REAL
// ---------------------------------------------------------------------------

function centrarTextoV(ptX, ptY, ptH, itemTexto) {
    try {
        var b = itemTexto.parent.bounds;
        var textoH = b[3].value - b[1].value;
        var offY = (ptH - textoH) / 2;
        if (offY < 0) offY = 0;
        itemTexto.position = [new UnitValue(ptX,"pt"), new UnitValue(ptY+offY,"pt")];
    } catch(e) {}
}

// ---------------------------------------------------------------------------
// ENCONTRAR CAPA DE FONDO (backgroundLayer o última capa / "Fondo" o "plancha")
// ---------------------------------------------------------------------------

function encontrarCapaFondo(doc) {
    try { return doc.backgroundLayer; } catch(e) {}
    // Buscar por nombre
    var candidatos = ["fondo","plancha","background","bg","pagina","page","scan"];
    for (var i=doc.layers.length-1; i>=0; i--) {
        var n = doc.layers[i].name.toLowerCase();
        for (var j=0; j<candidatos.length; j++) {
            if (n.indexOf(candidatos[j])!==-1) return doc.layers[i];
        }
    }
    return doc.layers[doc.layers.length-1];
}

// ---------------------------------------------------------------------------
// BUSCAR ARCHIVO INPAINTED EN LA CARPETA
// Coincide con el nombre base de la página (sin extensión), cualquier extensión
// ---------------------------------------------------------------------------

function buscarInpainted(rutaCarpeta, nombreDoc) {
    var baseSinExt = nombreDoc.replace(/\.[^.]+$/, "");
    var extsImg = /\.(jpg|jpeg|png|tif|tiff|bmp|webp|psd|psb)$/i;

    // Busca el archivo cuyo nombre base coincida, sin importar extensión
    function buscarEnCarpeta(carpeta) {
        try {
            var todos = carpeta.getFiles();
            for (var i = 0; i < todos.length; i++) {
                if (todos[i] instanceof File && extsImg.test(todos[i].name)) {
                    var nBase = todos[i].name.replace(/\.[^.]+$/, "");
                    if (nBase === baseSinExt) return todos[i];
                }
            }
        } catch(e) {}
        return null;
    }

    // Buscar solo en la subcarpeta "inpainted" (donde BT guarda los inpainted)
    var subInpainted = new Folder(rutaCarpeta + "/inpainted");
    if (subInpainted.exists) return buscarEnCarpeta(subInpainted);

    return null;
}

// ---------------------------------------------------------------------------
// IMPORTAR IMAGEN INPAINTED COMO CAPA JUSTO ENCIMA DEL FONDO
// ---------------------------------------------------------------------------

function importarInpainted(doc, archivoInp) {
    try {
        // Cargar como objeto inteligente (Place)
        var idPlc = charIDToTypeID("Plc ");
        var desc = new ActionDescriptor();
        desc.putPath(charIDToTypeID("null"), new File(archivoInp.fsName));
        desc.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
        executeAction(idPlc, desc, DialogModes.NO);

        var capaInp = doc.activeLayer;
        capaInp.name = "Inpainted";

        // Aplanar la transformación si quedó en modo Place (presionar Enter)
        try {
            var idCnfm = charIDToTypeID("Cnfm");
            var descCnfm = new ActionDescriptor();
            executeAction(idCnfm, descCnfm, DialogModes.NO);
        } catch(e) {}

        // Mover justo encima de la capa de fondo
        var capaFondo = encontrarCapaFondo(doc);
        if (capaFondo) {
            try {
                capaInp.move(capaFondo, ElementPlacement.PLACEBEFORE);
            } catch(e) {}
        }

        return capaInp;
    } catch(e) {
        throw new Error("No se pudo importar la plancha inpainted:\n" + e.toString());
    }
}

// ---------------------------------------------------------------------------
// NÚCLEO: aplicar la plantilla TraduBT (tamaño+guías, o Acción) al doc activo
// ---------------------------------------------------------------------------
// Sin comprobaciones de seguridad — las hace quien lo llame, según el
// contexto (tras insertar textos, o al pre-formatear planchas vacías).
// Lanza una excepción si algo falla; devuelve el modo aplicado ("archivo"/"accion").
function aplicarPlantillaCore(doc) {
    var descCfg = app.getCustomOptions("NavajaCRG_BT_Config"); // lanza si no existe

    var modo = "archivo";
    try { modo = descCfg.getString(stringIDToTypeID("bt_modoPlantilla")); } catch(e) {}

    if (modo === "accion") {
        var setAccion = "", nombreAccion = "";
        try { setAccion    = descCfg.getString(stringIDToTypeID("bt_accionSet")); }    catch(e) {}
        try { nombreAccion = descCfg.getString(stringIDToTypeID("bt_accionNombre")); } catch(e) {}
        if (!setAccion || !nombreAccion) throw new Error("No hay Set/Nombre de Acción configurados en TraduBT.");
        app.doAction(nombreAccion, setAccion);

    } else {
        var ancho = descCfg.getInteger(stringIDToTypeID("bt_ancho"));
        var alto  = descCfg.getInteger(stringIDToTypeID("bt_alto"));
        var resolucion = descCfg.getInteger(stringIDToTypeID("bt_resolucion"));

        doc.resizeImage(undefined, undefined, resolucion, ResampleMethod.NONE);
        doc.resizeImage(
            new UnitValue(ancho, "px"), new UnitValue(alto, "px"),
            resolucion, ResampleMethod.BICUBIC
        );

        try {
            var descGuias = app.getCustomOptions("NavajaCRG_BT_Guias");
            var totalH = descGuias.getInteger(stringIDToTypeID("guias_totalH"));
            var totalV = descGuias.getInteger(stringIDToTypeID("guias_totalV"));
            doc.guides.removeAll();
            for (var gh = 0; gh < totalH; gh++) {
                var posH = descGuias.getInteger(stringIDToTypeID("guia_H_" + gh));
                doc.guides.add(Direction.HORIZONTAL, new UnitValue(posH, "px"));
            }
            for (var gv = 0; gv < totalV; gv++) {
                var posV = descGuias.getInteger(stringIDToTypeID("guia_V_" + gv));
                doc.guides.add(Direction.VERTICAL, new UnitValue(posV, "px"));
            }
        } catch(eG) {
            // Sin guías guardadas (plantilla detectada desde JPG/PNG, p.ej.) — seguir sin ellas
        }
    }
    return modo;
}

// ---------------------------------------------------------------------------
// GUARDAR UN DOCUMENTO SOBRESCRIBIENDO EL ARCHIVO ORIGINAL, EN SU MISMO FORMATO
// ---------------------------------------------------------------------------
function guardarComoFormatoOriginal(doc, archivoOriginal) {
    var ext = archivoOriginal.name.replace(/^.*\./, "").toLowerCase();
    if (ext === "jpg" || ext === "jpeg") {
        var optsJ = new JPEGSaveOptions();
        optsJ.quality = 10;
        doc.saveAs(archivoOriginal, optsJ, true, Extension.LOWERCASE);
    } else if (ext === "png") {
        doc.saveAs(archivoOriginal, new PNGSaveOptions(), true, Extension.LOWERCASE);
    } else if (ext === "tif" || ext === "tiff") {
        doc.saveAs(archivoOriginal, new TiffSaveOptions(), true, Extension.LOWERCASE);
    } else if (ext === "psd" || ext === "psb") {
        doc.saveAs(archivoOriginal, new PhotoshopSaveOptions(), true, Extension.LOWERCASE);
    } else {
        doc.saveAs(archivoOriginal);
    }
}

// ---------------------------------------------------------------------------
// FLUJO: FORMATEAR TODAS LAS PLANCHAS DE UNA CARPETA (ANTES de traducir)
// ---------------------------------------------------------------------------
// Aplica la plantilla TraduBT (tamaño+guías, o Acción) a cada imagen de la
// carpeta del proyecto, SOBRESCRIBIENDO el archivo original (mismo nombre,
// mismo sitio) — importante porque BallonsTranslator detectará los globos
// sobre estas imágenes ya formateadas, así que el tamaño final debe ser el
// definitivo antes de traducir. Al terminar, ofrece abrir BallonsTranslator.
function flujoFormatearPlanchas() {
    var descCfgInicial;
    try { descCfgInicial = app.getCustomOptions("NavajaCRG_BT_Config"); }
    catch(e) {
        alert("⚠ No hay ninguna plantilla TraduBT guardada.\n\nVe a NavajaCRG-Preferencias → pestaña 'TraduBT' y guárdala primero.");
        return;
    }

    var carpeta = null;
    var carpetaGuardada = "";
    try { carpetaGuardada = descCfgInicial.getString(stringIDToTypeID("bt_carpetaProyectos")); } catch(e) {}
    if (carpetaGuardada) {
        var fCarpetaGuardada = new Folder(carpetaGuardada);
        if (fCarpetaGuardada.exists && confirm("¿Usar la carpeta de proyectos guardada?\n\n" + fCarpetaGuardada.fsName)) {
            carpeta = fCarpetaGuardada;
        }
    }
    if (!carpeta) {
        carpeta = Folder.selectDialog("Selecciona la carpeta con las planchas a formatear");
        if (!carpeta) return;
        guardarCarpetaProyectosBT(carpeta.fsName);
    }

    var modo = "archivo";
    try { modo = descCfgInicial.getString(stringIDToTypeID("bt_modoPlantilla")); } catch(e) {}

    var extsImg = /\.(jpg|jpeg|png|tif|tiff|psd|psb)$/i;
    var archivos = carpeta.getFiles(function(f) {
        return (f instanceof File) && extsImg.test(f.name);
    });

    if (!archivos.length) {
        alert("No se han encontrado imágenes en esa carpeta.");
        return;
    }

    if (!confirm(
        "Se van a SOBRESCRIBIR " + archivos.length + " archivo(s) en:\n" + carpeta.fsName + "\n\n" +
        "aplicándoles " + (modo === "accion" ? "la Acción de Photoshop configurada" : "la plantilla de tamaño/guías configurada") + ".\n\n" +
        "Esta acción NO se puede deshacer salvo que tengas copia de seguridad.\n\n¿Continuar?"
    )) return;

    var uO = app.preferences.rulerUnits;
    var uD = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS;
    app.displayDialogs = DialogModes.NO;

    var okCount = 0, errCount = 0;
    var errores = [];

    try {
        for (var i = 0; i < archivos.length; i++) {
            var f = archivos[i];
            try {
                var doc = app.open(f);
                aplicarPlantillaCore(doc);
                guardarComoFormatoOriginal(doc, f);
                doc.close(SaveOptions.DONOTSAVECHANGES);
                okCount++;
            } catch(eArch) {
                errCount++;
                errores.push(f.name + ": " + eArch.toString());
                try { if (app.documents.length) app.activeDocument.close(SaveOptions.DONOTSAVECHANGES); } catch(eClose) {}
            }
        }
    } finally {
        app.preferences.rulerUnits = uO;
        app.displayDialogs = uD;
    }

    var msg = "✓ " + okCount + " plancha(s) formateada(s) y sobrescrita(s)";
    if (errCount) msg += "\n\n⚠ " + errCount + " con error:\n" + errores.join("\n");
    alert(msg);

    // Ofrecer abrir BallonsTranslator para empezar a traducir ya sobre las
    // planchas formateadas.
    var rutaExe = "";
    try { rutaExe = descCfgInicial.getString(stringIDToTypeID("bt_rutaPrograma")); } catch(e) {}
    if (rutaExe && confirm("¿Abrir BallonsTranslator ahora para empezar a traducir estas planchas?")) {
        var fExe = new File(rutaExe);
        if (fExe.exists) {
            try { fExe.execute(); } catch(eExec) { alert("No se pudo abrir BallonsTranslator:\n" + eExec.toString()); }
        } else {
            alert("No se encuentra el ejecutable configurado:\n" + rutaExe);
        }
    }
}

// ---------------------------------------------------------------------------
// MODO C: SIN DOCUMENTO ABIERTO — BÚSQUEDA/APERTURA DE IMAGEN DE PÁGINA
// ---------------------------------------------------------------------------

// Busca la imagen original de una página por su nombre (clave del JSON),
// primero por coincidencia exacta y, si no existe, por nombre base con
// cualquier extensión de imagen habitual (igual criterio que buscarInpainted).
function buscarImagenPagina(rutaCarpeta, nombrePagina) {
    var carpeta = new Folder(rutaCarpeta);
    var directo = new File(rutaCarpeta + "/" + nombrePagina);
    if (directo.exists) return directo;

    var baseSinExt = nombrePagina.replace(/\.[^.]+$/, "");
    var extsImg = /\.(jpg|jpeg|png|tif|tiff|bmp|webp|psd|psb)$/i;
    try {
        var todos = carpeta.getFiles();
        for (var i = 0; i < todos.length; i++) {
            if (todos[i] instanceof File && extsImg.test(todos[i].name)) {
                var nBase = todos[i].name.replace(/\.[^.]+$/, "");
                if (nBase === baseSinExt) return todos[i];
            }
        }
    } catch(e) {}
    return null;
}

// Abre un archivo de imagen como documento nuevo sin diálogos de por medio.
// app.displayDialogs debe estar ya en DialogModes.NO antes de llamar a esto.
function abrirImagenSilenciosa(archivo) {
    var doc = app.open(archivo);
    try { doc.activeLayer.name = "Fondo"; } catch(e) {}
    return doc;
}

// ---------------------------------------------------------------------------
// MODO C: DIÁLOGO DE SELECCIÓN MÚLTIPLE DE PÁGINAS
// ---------------------------------------------------------------------------

function dialogoMultiPagina(datos, rutaCarpeta, jsonFile) {
    var pages = datos.pages || {};
    var nombresPag = [];
    for (var k in pages) if (pages.hasOwnProperty(k)) nombresPag.push(k);

    if (nombresPag.length === 0) {
        alert("El JSON no contiene páginas."); return null;
    }

    var nGlobosTotal = 0;
    for (var gi = 0; gi < nombresPag.length; gi++) {
        nGlobosTotal += (pages[nombresPag[gi]] || []).length;
    }

    var dlg = new Window("dialog", "BT → NavajaCRG  |  Importar varias páginas");
    dlg.alignChildren = ["fill","top"]; dlg.margins=18; dlg.spacing=10;

    // Info del proyecto
    var pI = dlg.add("panel", undefined, "Proyecto");
    pI.alignChildren = "left"; pI.margins=12;
    pI.add("statictext", undefined, "JSON : " + jsonFile.name);
    pI.add("statictext", undefined,
        "Páginas en JSON : " + nombresPag.length + "   |   Globos totales : " + nGlobosTotal);

    // Selección de páginas
    var pP = dlg.add("panel", undefined, "Páginas a importar");
    pP.alignChildren = "fill"; pP.margins=12; pP.spacing=6;

    var lista = pP.add("listbox", undefined, [], {multiselect:true});
    lista.preferredSize = [460, 160];
    for (var pj = 0; pj < nombresPag.length; pj++) {
        var nomPag = nombresPag[pj];
        var nGlobosPag = (pages[nomPag] || []).length;
        var it = lista.add("item", nomPag + "  (" + nGlobosPag + " globo" + (nGlobosPag===1?"":"s") + ")");
        it.paginaClave = nomPag;
        it.selected = true; // por defecto todas marcadas, como el diálogo de BT oficial
    }

    var gSel = pP.add("group"); gSel.orientation = "row";
    var bTodas = gSel.add("button", undefined, "Seleccionar todas");
    var bNinguna = gSel.add("button", undefined, "Deseleccionar todas");
    bTodas.onClick   = function(){ for (var i=0;i<lista.items.length;i++) lista.items[i].selected = true; };
    bNinguna.onClick = function(){ for (var i=0;i<lista.items.length;i++) lista.items[i].selected = false; };

    // Opciones
    var pO = dlg.add("panel", undefined, "Opciones");
    pO.alignChildren = "left"; pO.margins=12;
    var chkInp = pO.add("checkbox", undefined,
        "Incluir plancha inpainted (si existe, /inpainted/)");
    chkInp.value = true;

    // Botones
    var gB = dlg.add("group"); gB.alignment = "center"; gB.spacing = 10;
    gB.add("button", undefined, "Cancelar", {name:"cancel"}).preferredSize=[100,26];
    var bImport = gB.add("button", undefined, "Importar páginas seleccionadas", {name:"ok"});
    bImport.preferredSize = [220,26];

    if (dlg.show() !== 1) return null;

    var seleccionadas = [];
    for (var si = 0; si < lista.items.length; si++) {
        if (lista.items[si].selected) seleccionadas.push(lista.items[si].paginaClave);
    }
    if (seleccionadas.length === 0) { alert("No se seleccionó ninguna página."); return null; }

    return { paginas: seleccionadas, incluirInpainted: chkInp.value };
}

// ---------------------------------------------------------------------------
// MODO C: PROCESAR PÁGINAS SELECCIONADAS EN LOTE
// ---------------------------------------------------------------------------

function procesarPaginasBatch(datos, rutaCarpeta, seleccion, pf) {
    var paginas = seleccion.paginas;
    var incluirInpainted = seleccion.incluirInpainted;

    var abiertas = 0, conTexto = 0, conInpaint = 0, capasTotal = 0;
    var sinImagen = [], sinGlobos = [];

    for (var i = 0; i < paginas.length; i++) {
        var nombrePag = paginas[i];
        var numPag = numPagDesdNombre(nombrePag);
        if (!numPag) { sinImagen.push(nombrePag); continue; }

        var archivoImg = buscarImagenPagina(rutaCarpeta, nombrePag);
        if (!archivoImg) { sinImagen.push(nombrePag); continue; }

        var doc;
        try { doc = abrirImagenSilenciosa(archivoImg); }
        catch(eOpen) { sinImagen.push(nombrePag); continue; }

        abiertas++;

        var r = accionInsertarTextos(datos, doc, numPag, pf, false);
        if (r) {
            conTexto++;
            capasTotal += r.creadas;
        } else {
            sinGlobos.push(nombrePag);
        }

        if (incluirInpainted) {
            var archivoInp = buscarInpainted(rutaCarpeta, nombrePag);
            if (archivoInp) {
                try { importarInpainted(doc, archivoInp); conInpaint++; }
                catch(eInp) {}
            }
        }

        doc.activeLayer = doc.layers[0];
    }

    return {
        abiertas: abiertas, conTexto: conTexto, conInpaint: conInpaint,
        capasTotal: capasTotal,
        sinImagen: sinImagen, sinGlobos: sinGlobos
    };
}

// ---------------------------------------------------------------------------
// MODO C: FLUJO COMPLETO CUANDO NO HAY DOCUMENTO ABIERTO
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// GUARDAR CARPETA DE PROYECTOS EN NavajaCRG_BT_Config (sin tocar el resto)
// ---------------------------------------------------------------------------
function guardarCarpetaProyectosBT(rutaCarpeta) {
    try {
        var v = { rutaPrograma:"", modo:"archivo", ancho:1920, alto:2540, resolucion:300, accionSet:"", accionNombre:"" };
        try {
            var descExistente = app.getCustomOptions("NavajaCRG_BT_Config");
            try { v.rutaPrograma  = descExistente.getString(stringIDToTypeID("bt_rutaPrograma")); }      catch(e) {}
            try { v.modo          = descExistente.getString(stringIDToTypeID("bt_modoPlantilla")); }     catch(e) {}
            try { v.ancho         = descExistente.getInteger(stringIDToTypeID("bt_ancho")); }            catch(e) {}
            try { v.alto          = descExistente.getInteger(stringIDToTypeID("bt_alto")); }             catch(e) {}
            try { v.resolucion    = descExistente.getInteger(stringIDToTypeID("bt_resolucion")); }       catch(e) {}
            try { v.accionSet     = descExistente.getString(stringIDToTypeID("bt_accionSet")); }         catch(e) {}
            try { v.accionNombre  = descExistente.getString(stringIDToTypeID("bt_accionNombre")); }      catch(e) {}
        } catch(eNoExiste) {}

        var descBT = new ActionDescriptor();
        descBT.putString(stringIDToTypeID("bt_rutaPrograma"), v.rutaPrograma);
        descBT.putString(stringIDToTypeID("bt_carpetaProyectos"), rutaCarpeta);
        descBT.putString(stringIDToTypeID("bt_modoPlantilla"), v.modo);
        descBT.putInteger(stringIDToTypeID("bt_ancho"), v.ancho);
        descBT.putInteger(stringIDToTypeID("bt_alto"), v.alto);
        descBT.putInteger(stringIDToTypeID("bt_resolucion"), v.resolucion);
        descBT.putString(stringIDToTypeID("bt_accionSet"), v.accionSet);
        descBT.putString(stringIDToTypeID("bt_accionNombre"), v.accionNombre);
        app.putCustomOptions("NavajaCRG_BT_Config", descBT, true);
    } catch(e) {
        // No crítico — si falla, simplemente no se actualiza la carpeta guardada
    }
}

// ---------------------------------------------------------------------------
// DIÁLOGO INICIAL CUANDO NO HAY DOCUMENTO ABIERTO
// ---------------------------------------------------------------------------
// Busca un JSON de proyecto (imgtrans_*.json, o cualquier *.json si no hay
// ninguno con ese prefijo) dentro de la carpeta de proyectos guardada en
// NavajaCRG_BT_Config. Devuelve el File encontrado, o null si no hay carpeta
// guardada, no existe, o no contiene ningún JSON.
function buscarJsonEnCarpetaProyecto() {
    try {
        var descCfg = app.getCustomOptions("NavajaCRG_BT_Config");
        var rutaCarpeta = descCfg.getString(stringIDToTypeID("bt_carpetaProyectos"));
        if (!rutaCarpeta) return null;

        var carpeta = new Folder(rutaCarpeta);
        if (!carpeta.exists) return null;

        var todos = carpeta.getFiles("*.json");
        if (!todos.length) return null;

        // Preferir uno que empiece por "imgtrans_" (el que genera BallonsTranslator)
        for (var i = 0; i < todos.length; i++) {
            if (/^imgtrans_/i.test(todos[i].name)) return todos[i];
        }
        return todos[0];
    } catch(e) {
        return null;
    }
}

function dialogoInicioSinDocumento(jsonConfigurado) {
    var dlg = new Window("dialog", "BT → NavajaCRG");
    dlg.alignChildren = ["fill","top"]; dlg.margins = 18; dlg.spacing = 10;
    dlg.preferredSize.width = 480;

    dlg.add("statictext", undefined, "No hay ningún documento abierto. ¿Qué quieres hacer?");

    var pO = dlg.add("panel", undefined, "Acción");
    pO.alignChildren = "fill"; pO.margins = 14; pO.spacing = 8;

    var bFormatear = pO.add("button", undefined, "A)  Formatear planchas del proyecto (tamaño + guías)");
    bFormatear.preferredSize = [-1, 32];
    pO.add("statictext", undefined,
        "Aplica la plantilla TraduBT a TODAS las imágenes de una carpeta, ANTES de traducir.\n" +
        "Sobrescribe los archivos originales (mismo nombre, mismo sitio).",
        {multiline:true}).preferredSize = [-1, 32];

    pO.add("panel").preferredSize = [-1, 1];

    var bAbrirConfigurado = null;
    if (jsonConfigurado) {
        bAbrirConfigurado = pO.add("button", undefined, "B)  Abrir proyecto configurado");
        bAbrirConfigurado.preferredSize = [-1, 32];
        pO.add("statictext", undefined,
            "Usa directamente: " + jsonConfigurado.name,
            {multiline:true}).preferredSize = [-1, 25];
        pO.add("panel").preferredSize = [-1, 1];
    }

    var bImportar = pO.add("button", undefined,
        (jsonConfigurado ? "C)  " : "B)  ") + "Buscar nuevo proyecto (JSON)...");
    bImportar.preferredSize = [-1, 32];
    pO.add("statictext", undefined,
        "Inserta el texto ya traducido, leyendo el JSON que genera BallonsTranslator.",
        {multiline:true}).preferredSize = [-1, 26];

    var gB = dlg.add("group"); gB.alignment = "center";
    gB.add("button", undefined, "Cancelar", {name:"cancel"}).preferredSize = [100, 26];

    var accion = null;
    bFormatear.onClick = function(){ accion = "formatear"; dlg.close(1); };
    if (bAbrirConfigurado) bAbrirConfigurado.onClick = function(){ accion = "configurado"; dlg.close(1); };
    bImportar.onClick  = function(){ accion = "importar";  dlg.close(1); };

    return dlg.show() === 1 ? accion : null;
}

function flujoSinDocumento() {
    var jsonConfigurado = buscarJsonEnCarpetaProyecto();
    var accionInicial = dialogoInicioSinDocumento(jsonConfigurado);
    if (!accionInicial) return;
    if (accionInicial === "formatear") { flujoFormatearPlanchas(); return; }

    var jsonFile;
    if (accionInicial === "configurado") {
        jsonFile = jsonConfigurado;
    } else {
        jsonFile = File.openDialog("Selecciona el JSON de BallonsTranslator:", "*.json");
        if (!jsonFile) return;
    }

    var datos;
    try { datos = leerJsonBT(jsonFile.fsName); }
    catch(e) { alert("Error leyendo el JSON:\n" + e.toString()); return; }
    if (!datos || !datos.pages) {
        alert("El archivo no tiene el formato esperado de BallonsTranslator."); return;
    }

    var rutaCarpeta = jsonFile.parent.fsName;
    guardarCarpetaProyectosBT(rutaCarpeta); // recordar esta carpeta para la próxima vez
    var pf = cargarPlantillaCRG();

    var seleccion = dialogoMultiPagina(datos, rutaCarpeta, jsonFile);
    if (!seleccion) return;

    var uO = app.preferences.rulerUnits;
    var uT = app.preferences.typeUnits;
    var uD = app.displayDialogs;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits  = TypeUnits.POINTS;
    app.displayDialogs = DialogModes.NO;

    var res;
    try {
        res = procesarPaginasBatch(datos, rutaCarpeta, seleccion, pf);
    } finally {
        app.preferences.rulerUnits = uO;
        app.preferences.typeUnits  = uT;
        app.displayDialogs = uD;
    }

    var msg = "✓ " + res.abiertas + " página(s) abierta(s) en Photoshop\n" +
        res.conTexto + " con capas de texto insertadas (" + res.capasTotal + " capas en total)";
    if (seleccion.incluirInpainted) msg += "\n" + res.conInpaint + " con plancha inpainted importada";
    if (res.sinImagen.length) msg += "\n\n⚠ Sin imagen encontrada:\n" + res.sinImagen.join("\n");
    if (res.sinGlobos.length) msg += "\n\n⚠ Sin globos con traducción:\n" + res.sinGlobos.join("\n");
    if (!pf || !(pf.tamano > 0)) msg += "\n\n⚠ Plantilla NavajaCRG no encontrada — fuente por defecto.";

    alert(msg);
}

// ---------------------------------------------------------------------------
// ACCIÓN PRINCIPAL: INSERTAR CAPAS DE TEXTO (con delimitadores)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// ANALIZAR GRUPO EXISTENTE
// Devuelve { existe, capas:[{nombre,idx}], nuevos:[idx en ord sin capa] }
// ---------------------------------------------------------------------------

function analizarGrupoExistente(doc, numPag, ord) {
    var nomGrupo = "BT_Textos_Pag_" + numPag;
    var resultado = { existe: false, grupo: null, capas: [], nuevos: [] };
    try {
        var g = doc.layerSets.getByName(nomGrupo);
        resultado.existe = true;
        resultado.grupo  = g;

        // Recoger capas de texto del grupo
        for (var i = 0; i < g.artLayers.length; i++) {
            var lyr = g.artLayers[i];
            resultado.capas.push({ nombre: lyr.name, layer: lyr });
        }

        // Detectar globos del JSON sin capa correspondiente
        for (var i = 0; i < ord.length; i++) {
            var numGlobo = padNum(i+1, 2);
            var nomEsp   = "T-" + numPag + "-" + numGlobo;
            var encontrado = false;
            for (var j = 0; j < resultado.capas.length; j++) {
                if (resultado.capas[j].nombre === nomEsp) { encontrado = true; break; }
            }
            if (!encontrado) resultado.nuevos.push(i); // índice en ord
        }
    } catch(e) { /* grupo no existe */ }
    return resultado;
}

// ---------------------------------------------------------------------------
// INSERTAR / ACTUALIZAR UN SOLO GLOBO  (índice en ord)
// ---------------------------------------------------------------------------

function accionInsertarUnGlobo(datos, doc, numPag, pf, idxOrd, grupo) {
    var pages = datos.pages || {};
    var imgInfo = datos.image_info || {};

    var bl = null, nombreImg = null;
    for (var img in pages) {
        if (pages.hasOwnProperty(img) && numPagDesdNombre(img) === numPag) {
            bl = pages[img]; nombreImg = img; break;
        }
    }
    if (!bl || !bl.length) return false;

    var info     = imgInfo[nombreImg] || {};
    // Usar dimensiones de image_info si están; si no, usar el ancho del doc
    // (las coordenadas BT están en px de la imagen original; si no hay width
    //  guardado asumimos que la imagen original == dimensiones del doc abierto)
    var anchoImg = (info.width && info.width > 1) ? info.width : doc.width.as("px");
    var docPxW   = doc.width.as("px");
    var factor   = (docPxW / anchoImg) * 72 / doc.resolution;

    var usaPF = (pf !== null && pf.tamano > 0);
    var tamPt = usaPF ? pf.tamano : 10;
    var ord   = ordenar(bl);

    if (idxOrd < 0 || idxOrd >= ord.length) return false;
    var b = ord[idxOrd];
    var numGlobo = padNum(idxOrd+1, 2);
    var nomCapa  = "T-" + numPag + "-" + numGlobo;

    // Coordenadas
    var bx, by, bw, bh;
    if (b._bounding_rect && b._bounding_rect.length >= 4) {
        bx=b._bounding_rect[0]; by=b._bounding_rect[1];
        bw=b._bounding_rect[2]; bh=b._bounding_rect[3];
    } else if (b.xyxy && b.xyxy.length >= 4) {
        bx=b.xyxy[0]; by=b.xyxy[1];
        bw=b.xyxy[2]-b.xyxy[0]; bh=b.xyxy[3]-b.xyxy[1];
    } else { return false; }
    if (bw<4||bh<4) return false;

    var ptX=bx*factor, ptY=by*factor, ptW=bw*factor, ptH=bh*factor;
    if (ptW<1||ptH<1) return false;

    var tradRaw = unirLineas(b.translation);
    tradRaw = trim(tradRaw);
    if (!tradRaw.length) return false;

    var resultado = procesarFormatoMarkdown(tradRaw, usaPF ? pf.delimitadores : []);
    var textoLimpio = aOracion(resultado.texto);
    if (!textoLimpio.length) return false;

    // Eliminar capa existente con ese nombre si la hay
    try {
        var viejaLyr = grupo.artLayers.getByName(nomCapa);
        viejaLyr.remove();
    } catch(e) {}

    try {
        var capa = doc.artLayers.add();
        capa.kind = LayerKind.TEXT;
        capa.name = nomCapa;
        capa.move(grupo, ElementPlacement.PLACEATBEGINNING);
        doc.activeLayer = capa;

        var ti = capa.textItem;
        ti.kind     = TextType.PARAGRAPHTEXT;
        ti.contents = textoLimpio;

        if (usaPF) {
            try { ti.font = pf.nombre; } catch(ef) { try { ti.font = pf.familia; } catch(ef2) {} }
            ti.size = new UnitValue(pf.tamano, "pt");
            ti.color = crearColor(pf.colorR||0, pf.colorG||0, pf.colorB||0);
            ti.justification = justifPS(pf.justif);
            ti.antiAliasMethod = antiAliasPS(pf.antiAlias);
            if (pf.autoInterlin) { ti.autoLeadingAmount = 120; }
            else if (pf.interlineado > 0) { ti.leading = new UnitValue(pf.interlineado, "pt"); }
            if (pf.tracking)  ti.tracking = pf.tracking;
            if (pf.escalaH && pf.escalaH!==100) ti.horizontalScale = pf.escalaH;
            if (pf.escalaV && pf.escalaV!==100) ti.verticalScale   = pf.escalaV;
            if (pf.todoMayusc) ti.capitalization = TextCase.ALLCAPS;
        } else {
            ti.size = new UnitValue(tamPt, "pt");
            ti.color = crearColor(0,0,0);
            ti.justification = Justification.CENTER;
            ti.antiAliasMethod = AntiAlias.STRONG;
            ti.autoLeadingAmount = 120;
        }

        ti.position = [new UnitValue(ptX,"pt"), new UnitValue(ptY,"pt")];
        ti.width    = new UnitValue(ptW, "pt");
        ti.height   = new UnitValue(Math.max(ptH, tamPt*1.2), "pt");

        if (usaPF) aplicarFormatoBase(pf, 0, textoLimpio.length);
        centrarTextoV(ptX, ptY, ptH, ti);
        ti.contents = textoLimpio;

        if (usaPF && resultado.formatos.length > 0) {
            var fmtsGrp = [];
            for (var fi=0; fi<resultado.formatos.length; fi++) {
                var fm = resultado.formatos[fi];
                var found=false;
                for (var fj=0; fj<fmtsGrp.length; fj++) {
                    if (fmtsGrp[fj].inicio===fm.inicio && fmtsGrp[fj].fin===fm.fin) {
                        fmtsGrp[fj].delims.push(fm.delim); found=true; break;
                    }
                }
                if (!found) fmtsGrp.push({inicio:fm.inicio, fin:fm.fin, delims:[fm.delim]});
            }
            for (var fi=0; fi<fmtsGrp.length; fi++) {
                aplicarEstiloRango(pf, fmtsGrp[fi].inicio, fmtsGrp[fi].fin, fmtsGrp[fi].delims);
            }
        }
        if (usaPF) aplicarAntiAliasACapaActual(pf.antiAlias);
        return true;
    } catch(e) { return false; }
}

// ---------------------------------------------------------------------------
// DIÁLOGO DE CONFLICTO — grupo ya existe
// Devuelve { modo:"todo"|"uno"|"nuevos"|null, idxOrd:N }
// ---------------------------------------------------------------------------

function dialogoConflicto(doc, numPag, analisis, datos, capaActiva) {
    var pages = datos.pages || {};
    var bl = null;
    for (var img in pages) {
        if (pages.hasOwnProperty(img) && numPagDesdNombre(img) === numPag) {
            bl = pages[img]; break;
        }
    }
    var ord = bl ? ordenar(bl) : [];

    // Detectar globo preseleccionado desde la capa activa  (T-XX-YY)
    var preselIdx = -1;
    if (capaActiva) {
        var m = capaActiva.match(/^T-\d+-([0-9]+)$/);
        if (m) {
            var numGlobo = parseInt(m[1], 10);
            // numGlobo es 1-based desde el final de ord  →  idxOrd = ord.length - numGlobo
            preselIdx = numGlobo - 1;
            if (preselIdx < 0 || preselIdx >= ord.length) preselIdx = -1;
        }
    }

    var hayNuevos = (analisis.nuevos.length > 0);

    var dlg = new Window("dialog", "BT → NavajaCRG  |  Grupo existente — Pág. " + numPag);
    dlg.alignChildren = ["fill","top"]; dlg.margins=18; dlg.spacing=10;

    // Info situación
    var pI = dlg.add("panel", undefined, "Situación");
    pI.alignChildren = "left"; pI.margins=12;
    pI.add("statictext", undefined,
        "El grupo «BT_Textos_Pag_" + numPag + "» ya existe con " +
        analisis.capas.length + " capa(s) de texto.");
    if (hayNuevos) {
        var lN = pI.add("statictext", undefined,
            "⚠  Hay " + analisis.nuevos.length + " globo(s) nuevo(s) en el JSON sin capa.");
        lN.graphics.foregroundColor =
            lN.graphics.newPen(lN.graphics.PenType.SOLID_COLOR,[0.9,0.6,0],1);
    }

    // Opciones
    var pO = dlg.add("panel", undefined, "¿Qué deseas hacer?");
    pO.alignChildren = "fill"; pO.margins=14; pO.spacing=10;

    // Opción 1 — sobreescribir todo
    var bTodo = pO.add("button", undefined, "Sobreescribir todo el grupo");
    bTodo.preferredSize = [-1, 28];
    pO.add("statictext", undefined,
        "Elimina el grupo actual y vuelve a crear todas las capas desde el JSON.",
        {multiline:true}).preferredSize=[-1,24];

    pO.add("panel").preferredSize=[-1,1];

    // Opción 2 — un globo concreto
    var gUno = pO.add("group"); gUno.alignChildren=["left","center"]; gUno.spacing=6;
    var bUno = gUno.add("button", undefined, "Actualizar globo:");
    bUno.preferredSize = [130, 28];

    // Construir lista desplegable: T-XX-01 … T-XX-NN  (orden visual = 01 arriba)
    var opciones = [];
    for (var i = 0; i < ord.length; i++) {
        var numG = padNum(i+1, 2);
        var trad = trim(unirLineas(ord[i].translation)).slice(0, 40);
        opciones.push("T-" + numPag + "-" + numG + "  |  " + trad);
    }
    var drop = gUno.add("dropdownlist", undefined, opciones);
    drop.preferredSize = [320, 24];
    // Preseleccionar
    if (preselIdx >= 0 && preselIdx < opciones.length) {
        drop.selection = preselIdx;
    } else {
        drop.selection = 0;
    }

    pO.add("statictext", undefined,
        "Actualiza solo el globo seleccionado (o el que tengas activo en capas).",
        {multiline:true}).preferredSize=[-1,24];

    // Opción 3 — solo nuevos (solo si los hay)
    var bNuevos = null;
    if (hayNuevos) {
        pO.add("panel").preferredSize=[-1,1];
        bNuevos = pO.add("button", undefined,
            "Añadir solo los " + analisis.nuevos.length + " globo(s) nuevo(s)");
        bNuevos.preferredSize = [-1, 28];
        pO.add("statictext", undefined,
            "Mantiene las capas existentes y añade solo los globos que faltan.",
            {multiline:true}).preferredSize=[-1,24];
    }

    // Opción 4 — importar/sobreescribir inpainted
    pO.add("panel").preferredSize=[-1,1];
    var tieneCapaInp = false;
    try { doc.layers.getByName("Inpainted"); tieneCapaInp = true; } catch(e) {}
    var bInpainted = pO.add("button", undefined,
        tieneCapaInp ? "Sobreescribir plancha inpainted" : "Importar plancha inpainted");
    bInpainted.preferredSize = [-1, 28];
    pO.add("statictext", undefined,
        tieneCapaInp
            ? "Elimina la capa Inpainted actual y la reimporta desde la carpeta."
            : "Importa el inpainted de la página encima del Fondo (sin tocar los textos).",
        {multiline:true}).preferredSize=[-1,24];

    // Cancelar
    var gC = dlg.add("group"); gC.alignment="center";
    gC.add("button", undefined, "Cancelar", {name:"cancel"}).preferredSize=[100,26];

    var resultado = null;

    bTodo.onClick = function() { resultado = {modo:"todo",       idxOrd:-1};   dlg.close(1); };
    bUno.onClick  = function() {
        var sel = drop.selection ? drop.selection.index : 0;
        resultado = {modo:"uno", idxOrd:sel};
        dlg.close(1);
    };
    if (bNuevos) {
        bNuevos.onClick = function() { resultado = {modo:"nuevos",    idxOrd:-1}; dlg.close(1); };
    }
    bInpainted.onClick = function() { resultado = {modo:"inpainted", idxOrd:-1}; dlg.close(1); };

    return dlg.show()===1 ? resultado : null;
}

function accionInsertarTextos(datos, doc, numPag, pf, soloNuevos) {
    var pages = datos.pages || {};
    var imgInfo = datos.image_info || {};

    var bl = null, nombreImg = null;
    for (var img in pages) {
        if (pages.hasOwnProperty(img) && numPagDesdNombre(img) === numPag) {
            bl = pages[img]; nombreImg = img; break;
        }
    }
    if (!bl || !bl.length) return null;

    var info     = imgInfo[nombreImg] || {};
    // Si image_info no tiene width (BT no procesó la página aún), usar doc dimensions
    var anchoImg = (info.width  && info.width  > 1) ? info.width  : doc.width.as("px");
    var altoImg  = (info.height && info.height > 1) ? info.height : doc.height.as("px");
    var docPxW   = doc.width.as("px");
    var escX     = docPxW / anchoImg;
    var docRes   = doc.resolution;
    var factor   = escX * 72 / docRes;   // px_BT → pt universales

    var usaPF = (pf !== null && pf.tamano > 0);
    var tamPt = usaPF ? pf.tamano : 10;

    var ord = ordenar(bl);
    var nomGrupo = "BT_Textos_Pag_" + numPag;
    var grupo;
    if (soloNuevos) {
        try { grupo = doc.layerSets.getByName(nomGrupo); } catch(e) {}
        if (!grupo) { grupo = doc.layerSets.add(); grupo.name = nomGrupo; }
    } else {
        try { doc.layerSets.getByName(nomGrupo).remove(); } catch(e) {}
        grupo = doc.layerSets.add();
        grupo.name = nomGrupo;
    }

    var creadas = 0, omitidas = 0;

    for (var i = ord.length-1; i >= 0; i--) {
        // Si solo añadimos nuevos, saltar los que ya tienen capa
        if (soloNuevos) {
            var numGloboChk = padNum(i+1, 2);
            var nomCapaChk  = "T-" + numPag + "-" + numGloboChk;
            var yaExiste = false;
            try { grupo.artLayers.getByName(nomCapaChk); yaExiste=true; } catch(e) {}
            if (yaExiste) { continue; }
        }
        var b = ord[i];

        // Coordenadas en px BT
        var bx, by, bw, bh;
        if (b._bounding_rect && b._bounding_rect.length >= 4) {
            bx=b._bounding_rect[0]; by=b._bounding_rect[1];
            bw=b._bounding_rect[2]; bh=b._bounding_rect[3];
        } else if (b.xyxy && b.xyxy.length >= 4) {
            bx=b.xyxy[0]; by=b.xyxy[1];
            bw=b.xyxy[2]-b.xyxy[0]; bh=b.xyxy[3]-b.xyxy[1];
        } else { omitidas++; continue; }

        if (bw<4 || bh<4) { omitidas++; continue; }

        // Convertir a pt
        var ptX = bx*factor, ptY = by*factor, ptW = bw*factor, ptH = bh*factor;
        if (ptW<1 || ptH<1) { omitidas++; continue; }

        // Texto de traducción (con posibles delimitadores)
        var tradRaw = unirLineas(b.translation);
        tradRaw = trim(tradRaw);
        if (!tradRaw.length) { omitidas++; continue; }

        // Procesar delimitadores
        var resultado = procesarFormatoMarkdown(tradRaw, usaPF ? pf.delimitadores : []);
        var textoLimpio = resultado.texto;
        if (!textoLimpio.length) { omitidas++; continue; }

        // Aplicar formato oración al texto ya limpio de delimitadores
        textoLimpio = aOracion(textoLimpio);

        try {
            var capa = doc.artLayers.add();
            capa.kind = LayerKind.TEXT;
            capa.name = "T-" + numPag + "-" + padNum(i+1, 2);
            capa.move(grupo, ElementPlacement.PLACEATBEGINNING);
            doc.activeLayer = capa;

            var ti = capa.textItem;
            ti.kind     = TextType.PARAGRAPHTEXT;
            ti.contents = textoLimpio;

            if (usaPF) {
                try { ti.font = pf.nombre; } catch(ef) {
                    try { ti.font = pf.familia; } catch(ef2) {}
                }
                ti.size = new UnitValue(pf.tamano, "pt");
                ti.color = crearColor(pf.colorR||0, pf.colorG||0, pf.colorB||0);
                ti.justification = justifPS(pf.justif);
                ti.antiAliasMethod = antiAliasPS(pf.antiAlias);
                if (pf.autoInterlin) {
                    ti.autoLeadingAmount = 120;
                } else if (pf.interlineado > 0) {
                    ti.leading = new UnitValue(pf.interlineado, "pt");
                }
                if (pf.tracking)            ti.tracking       = pf.tracking;
                if (pf.escalaH && pf.escalaH!==100) ti.horizontalScale = pf.escalaH;
                if (pf.escalaV && pf.escalaV!==100) ti.verticalScale   = pf.escalaV;
                if (pf.todoMayusc) ti.capitalization = TextCase.ALLCAPS;
            } else {
                ti.size = new UnitValue(tamPt, "pt");
                ti.color = crearColor(0,0,0);
                ti.justification = Justification.CENTER;
                ti.antiAliasMethod = AntiAlias.STRONG;
                ti.autoLeadingAmount = 120;
            }

            // Posición y dimensiones
            ti.position = [new UnitValue(ptX,"pt"), new UnitValue(ptY,"pt")];
            ti.width    = new UnitValue(ptW, "pt");
            ti.height   = new UnitValue(Math.max(ptH, tamPt*1.2), "pt");

            // Aplicar estilo base completo vía AM (fuerza familia/estilo/color uniforme)
            if (usaPF) {
                aplicarFormatoBase(pf, 0, textoLimpio.length);
            }

            // Centrado vertical
            centrarTextoV(ptX, ptY, ptH, ti);
            // Reafirmar contenido tras centrar
            ti.contents = textoLimpio;

            // Aplicar delimitadores
            if (usaPF && resultado.formatos.length > 0) {
                // Agrupar formatos superpuestos
                var fmtsGrp = [];
                for (var fi=0; fi<resultado.formatos.length; fi++) {
                    var fm = resultado.formatos[fi];
                    var found=false;
                    for (var fj=0; fj<fmtsGrp.length; fj++) {
                        if (fmtsGrp[fj].inicio===fm.inicio && fmtsGrp[fj].fin===fm.fin) {
                            fmtsGrp[fj].delims.push(fm.delim); found=true; break;
                        }
                    }
                    if (!found) fmtsGrp.push({inicio:fm.inicio, fin:fm.fin, delims:[fm.delim]});
                }
                for (var fi=0; fi<fmtsGrp.length; fi++) {
                    aplicarEstiloRango(pf, fmtsGrp[fi].inicio, fmtsGrp[fi].fin, fmtsGrp[fi].delims);
                }
            }

            // Forzar anti-alias final
            if (usaPF) aplicarAntiAliasACapaActual(pf.antiAlias);

            creadas++;
        } catch(eC) { omitidas++; }
    }

    doc.activeLayer = grupo;
    return {
        creadas: creadas, omitidas: omitidas, grupo: nomGrupo,
        usaPF: usaPF, fuente: usaPF ? (pf.familia||pf.nombre) : "(fallback)"
    };
}

// ---------------------------------------------------------------------------
// DIÁLOGO PRINCIPAL
// ---------------------------------------------------------------------------

function dialogo(datos, rutaCarpeta, numPag, jsonFile, docNombre, doc) {
    var pages = datos.pages || {};
    var nPags=0, nGlobos=0, tienePag=false;
    for (var k in pages) {
        if (!pages.hasOwnProperty(k)) continue;
        nPags++; nGlobos += (pages[k]||[]).length;
        if (numPagDesdNombre(k) === numPag) tienePag=true;
    }

    // Buscar inpainted
    var archivoInp = buscarInpainted(rutaCarpeta, docNombre);
    var tieneInp   = (archivoInp !== null);

    var dlg = new Window("dialog", "BT → NavajaCRG  |  Importar página");
    dlg.alignChildren = ["fill","top"]; dlg.margins=18; dlg.spacing=10;

    // Info
    var pI = dlg.add("panel", undefined, "Proyecto");
    pI.alignChildren = "left"; pI.margins=12;
    pI.add("statictext", undefined, "JSON : " + jsonFile.name);
    pI.add("statictext", undefined, "Páginas en JSON : " + nPags + "   |   Globos totales : " + nGlobos);
    var lPag = pI.add("statictext", undefined,
        "Página activa : " + numPag + (tienePag ? "  ✓" : "  ✗ (no está en el JSON)"));
    if (!tienePag) lPag.graphics.foregroundColor =
        lPag.graphics.newPen(lPag.graphics.PenType.SOLID_COLOR,[0.9,0.3,0],1);

    // Comprobación de formato/plantilla TraduBT (punto 3): en modo "archivo"
    // comparamos tamaño real vs. plantilla guardada; en modo "accion" no hay
    // un tamaño numérico de referencia, así que solo informamos del tamaño
    // actual y si el documento tiene guías o no.
    var lFormato = pI.add("statictext", undefined, "", {multiline:true});
    lFormato.preferredSize = [-1, 28];
    try {
        var descCfgChk = app.getCustomOptions("NavajaCRG_BT_Config");
        var modoChk = "archivo";
        try { modoChk = descCfgChk.getString(stringIDToTypeID("bt_modoPlantilla")); } catch(e) {}

        var anchoDoc = Math.round(doc.width.as("px"));
        var altoDoc  = Math.round(doc.height.as("px"));

        if (modoChk === "accion") {
            var tieneGuiasDoc = (doc.guides.length > 0);
            lFormato.text = "Formato actual : " + anchoDoc + "×" + altoDoc + " px" +
                (tieneGuiasDoc ? "  |  con guías" : "  |  SIN guías");
            lFormato.graphics.foregroundColor = lFormato.graphics.newPen(
                lFormato.graphics.PenType.SOLID_COLOR, tieneGuiasDoc ? [0.6,0.6,0.6] : [0.8,0.6,0], 1);
        } else {
            var anchoPlant = descCfgChk.getInteger(stringIDToTypeID("bt_ancho"));
            var altoPlant  = descCfgChk.getInteger(stringIDToTypeID("bt_alto"));
            var coincide = (anchoDoc === anchoPlant && altoDoc === altoPlant);
            lFormato.text = coincide
                ? "✓ Formato coincide con la plantilla TraduBT (" + anchoPlant + "×" + altoPlant + " px)"
                : "⚠ Esta página (" + anchoDoc + "×" + altoDoc + " px) NO coincide con la plantilla TraduBT (" + anchoPlant + "×" + altoPlant + " px)";
            lFormato.graphics.foregroundColor = lFormato.graphics.newPen(
                lFormato.graphics.PenType.SOLID_COLOR, coincide ? [0,0.7,0] : [0.9,0.2,0], 1);
        }
    } catch(eChk) {
        lFormato.text = "(Sin plantilla TraduBT guardada — no se puede comprobar el formato)";
        lFormato.graphics.foregroundColor = lFormato.graphics.newPen(
            lFormato.graphics.PenType.SOLID_COLOR, [0.5,0.5,0.5], 1);
    }

    // Inpainted info
    var lInp = pI.add("statictext", undefined,
        "Inpainted : " + (tieneInp ? "✓  " + archivoInp.name : "✗  No encontrado en la carpeta"));
    if (!tieneInp) lInp.graphics.foregroundColor =
        lInp.graphics.newPen(lInp.graphics.PenType.SOLID_COLOR,[0.5,0.5,0.5],1);

    // Acciones
    var pO = dlg.add("panel", undefined, "Acción");
    pO.alignChildren = "fill"; pO.margins=14; pO.spacing=8;

    // A
    var bA = pO.add("button", undefined,
        "A)  Insertar capas de texto en la página activa  (Pág. " + numPag + ")");
    bA.preferredSize = [-1, 32]; bA.enabled = tienePag;
    pO.add("statictext", undefined,
        "Crea el grupo «BT_Textos_Pag_" + numPag + "» con un TextLayer por globo.\n" +
        "Coordenadas universales (72/300 ppp).",
        {multiline:true}).preferredSize = [-1, 30];

    pO.add("panel").preferredSize = [-1,1];

    // B
    var bB = pO.add("button", undefined,
        "B)  Insertar capas de texto  +  plancha inpainted");
    bB.preferredSize = [-1, 32]; bB.enabled = (tienePag && tieneInp);
    var lblB = pO.add("statictext", undefined,
        "Igual que A y además importa inpainted justo encima de fondo.\n" +
        (tieneInp ? ("Archivo: " + archivoInp.name) : "⚠ No hay inpainted en la carpeta."),
        {multiline:true});
    lblB.preferredSize = [-1, 30];
    if (!tieneInp) lblB.graphics.foregroundColor =
        lblB.graphics.newPen(lblB.graphics.PenType.SOLID_COLOR,[0.9,0.3,0],1);

    var gB = dlg.add("group"); gB.alignment = "center";
    gB.add("button", undefined, "Cancelar", {name:"cancel"}).preferredSize=[100,26];

    var acc = null;
    bA.onClick = function(){ acc="A"; dlg.close(1); };
    bB.onClick = function(){ acc="B"; dlg.close(1); };

    return dlg.show()===1 ? {acc:acc, archivoInp:archivoInp} : null;
}

// ---------------------------------------------------------------------------
// MAIN
// ---------------------------------------------------------------------------

function main() {
    if (!app.documents.length) {
        flujoSinDocumento();
        return;
    }
    var doc = app.activeDocument;
    var rutaCarpeta;
    try { rutaCarpeta = doc.path.fsName; }
    catch(e) { alert("El documento no está guardado.\nGuárdalo primero (Ctrl+S)."); return; }

    var numPag = "00";
    try {
        var m = doc.name.replace(/\.[^.]+$/, "").match(/(\d+)$/);
        numPag = m ? padNum(parseInt(m[1],10), 2) : "00";
    } catch(e) {}

    // Buscar JSON automáticamente en la carpeta del documento
    var jsonFile = buscarJsonEnCarpeta(rutaCarpeta);
    if (!jsonFile) {
        // Si no lo encuentra, pedir al usuario
        jsonFile = File.openDialog(
            "No se encontró JSON en la carpeta.\nSelecciona el JSON de BallonsTranslator:",
            "*.json");
        if (!jsonFile) return;
    }

    var datos;
    try { datos = leerJsonBT(jsonFile.fsName); }
    catch(e) { alert("Error leyendo el JSON:\n" + e.toString()); return; }
    if (!datos || !datos.pages) {
        alert("El archivo no tiene el formato esperado de BallonsTranslator."); return;
    }

    // Cargar plantilla NavajaCRG (fuente + delimitadores)
    var pf = cargarPlantillaCRG();

    // ── Detectar si el grupo de texto ya existe ANTES de mostrar el diálogo ──
    // Si ya existe, saltamos el diálogo principal y vamos directo al de conflicto.
    var pages = datos.pages || {};
    var blCheck = null;
    for (var imgK in pages) {
        if (pages.hasOwnProperty(imgK) && numPagDesdNombre(imgK) === numPag) {
            blCheck = pages[imgK]; break;
        }
    }
    var ordCheck = blCheck ? ordenar(blCheck) : [];
    var analisis = analizarGrupoExistente(doc, numPag, ordCheck);

    // Nombre de la capa activa para preseleccionar globo en dialogoConflicto
    var nomCapaActiva = "";
    try { nomCapaActiva = doc.activeLayer.name; } catch(e) {}

    var res       = null;
    var modoFinal = "todo";
    var idxGloboUno = -1;

    if (analisis.existe) {
        // El grupo ya existe → mostrar directamente el diálogo de conflicto,
        // sin pasar por el diálogo principal A/B. La acción "sobreescribir todo"
        // equivale a A; las opciones de globo único y nuevos no necesitan elegir A/B.
        var resConflicto = dialogoConflicto(doc, numPag, analisis, datos, nomCapaActiva);
        if (!resConflicto) return;
        modoFinal   = resConflicto.modo;
        idxGloboUno = resConflicto.idxOrd;
        // Para la lógica de ejecución usamos acc="A" salvo que se quiera inpainted,
        // que en este flujo solo aplica en sobreescribir todo — lo pedimos ahora si procede.
        res = { acc: "A", archivoInp: null };
        if (modoFinal === "todo") {
            // Preguntar si también quiere importar el inpainted
            var archivoInp = buscarInpainted(rutaCarpeta, doc.name);
            if (archivoInp && confirm(
                "¿Importar también la plancha inpainted?\n\n" + archivoInp.name)) {
                res = { acc: "B", archivoInp: archivoInp };
            }
        }
    } else {
        // El grupo NO existe → flujo normal con el diálogo principal
        res = dialogo(datos, rutaCarpeta, numPag, jsonFile, doc.name, doc);
        if (!res) return;
    }

    // Guardar y restaurar unidades
    var uO = app.preferences.rulerUnits;
    var uT = app.preferences.typeUnits;
    app.preferences.rulerUnits = Units.PIXELS;
    app.preferences.typeUnits  = TypeUnits.POINTS;
    app.displayDialogs = DialogModes.NO;

    try {
        if (res.acc === "A" || res.acc === "B" || modoFinal === "inpainted") {

            var msg = "";

            if (modoFinal === "todo") {
                // ── Sobreescribir todo ──
                var rC = accionInsertarTextos(datos, doc, numPag, pf, false);
                if (!rC) { alert("Página " + numPag + " no encontrada o sin globos."); return; }
                msg = "✓ Capas insertadas — Pág. " + numPag + "\n\n" +
                    "Grupo : " + rC.grupo + "\n" +
                    "Capas : " + rC.creadas +
                    (rC.omitidas ? "   Omitidas : " + rC.omitidas : "") + "\n" +
                    (rC.usaPF
                        ? "Fuente NavajaCRG : " + rC.fuente + "\n" +
                          (pf.delimitadores && pf.delimitadores.length > 0
                              ? "Delimitadores activos : " + pf.delimitadores.length
                              : "Sin delimitadores configurados")
                        : "⚠ Plantilla NavajaCRG no encontrada — fuente por defecto.") +
                    "\nJSON : " + jsonFile.name;

            } else if (modoFinal === "uno") {
                // ── Actualizar un globo concreto ──
                var ok = accionInsertarUnGlobo(datos, doc, numPag, pf, idxGloboUno, analisis.grupo);
                var numGloboStr = padNum(idxGloboUno+1, 2);
                msg = ok
                    ? "✓ Globo actualizado: T-" + numPag + "-" + numGloboStr
                    : "⚠ No se pudo actualizar el globo T-" + numPag + "-" + numGloboStr;

            } else if (modoFinal === "nuevos") {
                // ── Solo añadir nuevos ──
                var rN = accionInsertarTextos(datos, doc, numPag, pf, true);
                if (!rN) { alert("No se pudo añadir globos nuevos."); return; }
                msg = "✓ Globos nuevos añadidos — Pág. " + numPag + "\n" +
                    "Añadidas : " + rN.creadas + " capa(s)\n" +
                    "JSON : " + jsonFile.name;

            } else if (modoFinal === "inpainted") {
                // ── Importar / sobreescribir solo el inpainted ──
                // Eliminar capa Inpainted existente si la hay
                try {
                    var capaVieja = doc.layers.getByName("Inpainted");
                    capaVieja.remove();
                } catch(e) {}

                var archivoInp = buscarInpainted(rutaCarpeta, doc.name);
                if (!archivoInp) {
                    if (confirm("No se encontró el inpainted automáticamente.\n\n¿Buscarlo manualmente?")) {
                        archivoInp = File.openDialog(
                            "Selecciona el inpainted de la página " + numPag,
                            "Imágenes:*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.webp;*.bmp"
                        );
                    }
                }
                if (archivoInp) {
                    try {
                        importarInpainted(doc, archivoInp);
                        msg = "✓ Plancha inpainted importada:\n" + archivoInp.name +
                              "\n(justo encima del fondo)";
                    } catch(eI) {
                        msg = "⚠ Error al importar la plancha:\n" + eI.toString();
                    }
                } else {
                    msg = "Operación cancelada — no se seleccionó ningún archivo.";
                }
            }

            if (res.acc === "B" && modoFinal === "todo") {
                try {
                    importarInpainted(doc, res.archivoInp);
                    msg += "\n\n✓ Plancha inpainted importada:\n" + res.archivoInp.name +
                           "\n(justo encima del fondo)";
                } catch(eI) {
                    msg += "\n\n⚠ Error al importar la plancha:\n" + eI.toString();
                }
            }

            alert(msg);
        }
    } finally {
        app.preferences.rulerUnits = uO;
        app.preferences.typeUnits  = uT;
        app.displayDialogs = DialogModes.ERROR;
    }
}

try { main(); }
catch(e) { alert("Error en BT_ImportarJSON.jsx:\n" + e.toString() + "\nLínea: " + e.line); }
