$(document).ready(function() {
  $("#boton1").click(function() {
    $("#contenido").html("Mostrando logs...");
  });
  
  $("#boton2").click(function() {
    $("#contenido").html("<pre style='color:#9055ff;'>from renderity_utils import apilog<br><br># Añadir nueva entrada a la consola<br>apilog().put('Nueva entrada')<br><br># Borrar logs<br>apilog().clear()</pre>");
  });
  
  $("#boton3").click(function() {
    $("#contenido").html('<form action="/upload" method="post" enctype="multipart/form-data"><div class="mb-3"><label for="archivo" class="form-label">Seleccionar archivo</label><input type="file" class="form-control" id="archivo" name="archivo"></div><button type="submit" class="btn btn-primary">Subir archivo</button></form>');
  });
  
  $("#boton4").click(function() {
    $("#contenido").html(
      <div class='container mt-4'>
        <div id='terminal-container'></div>
        <form id='command-form' class="mt-3">
          <div class='input-group'>
            <span class='input-group-text bg-dark text-light'>$</span>
            <input type='text' class='form-control bg-dark text-light' id='command-input' placeholder='Ingresa un comando'>
            <button type='submit' class='btn btn-outline-primary bg-dark'>EJECUTAR</button>
          </div>
        </form>
      </div>
    );
    
    // Inicializar la terminal con Xterm.js
    const terminal = new Terminal({
      rendererType: 'canvas',
      convertEol: true,
      fontFamily: 'Courier New, monospace',
      fontSize: 14,
      cursorBlink: true
    });
    terminal.open(document.getElementById('terminal-container'));
    
    // Manejar envío de comandos
    const commandForm = document.getElementById('command-form');
    const commandInput = document.getElementById('command-input');
    commandForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const command = commandInput.value.trim();
      if (!command) return;
      commandInput.value = "";
      terminal.writeln($ ${command});
      fetch("/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: command, mode: "bash" })
      })
      .then(response => response.json())
      .then(data => {
        const lastLine = data.history.slice(-1)[0] || "";
        terminal.writeln(lastLine);
      })
      .catch(err => {
        terminal.writeln("Error en la conexión.");
      });
    });
  });
});