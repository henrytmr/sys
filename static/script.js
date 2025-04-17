document.addEventListener('DOMContentLoaded', () => {
    const terminal = {
        history: document.getElementById('history'),
        input: document.getElementById('command'),
        executeBtn: document.getElementById('execute'),
        currentPath: document.getElementById('currentPath'),
        
        init() {
            this.setupEventListeners();
            this.resizeTerminal();
            window.addEventListener('resize', () => this.resizeTerminal());
        },
        
        setupEventListeners() {
            this.executeBtn.addEventListener('click', () => this.handleCommand());
            this.input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.handleCommand();
            });
            
            document.getElementById('file-input').addEventListener('change', (e) => {
                this.handleFileUpload(e.target.files[0]);
            });
        },
        
        async handleCommand() {
            const command = this.input.value.trim();
            if (!command) return;
            
            this.executeBtn.disabled = true;
            try {
                const response = await fetch('/execute', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command })
                });
                
                const data = await response.json();
                
                if (!response.ok) throw new Error(data.error || 'Command error');
                
                this.updateInterface(data);
                
            } catch (error) {
                this.displayError(error.message);
            } finally {
                this.input.value = '';
                this.executeBtn.disabled = false;
            }
        },
        
        updateInterface(data) {
            this.currentPath.textContent = data.cwd;
            this.history.innerHTML = data.history.map(item => `
                <div class="history-line">${item.replace(/\n/g, '<br>')}</div>
            `).join('');
            this.history.scrollTop = this.history.scrollHeight;
        },
        
        async handleFileUpload(file) {
            const formData = new FormData();
            formData.append('archivo', file);
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) throw new Error('Upload failed');
                window.location.reload();
                
            } catch (error) {
                this.displayError(error.message);
            }
        },
        
        async deleteFile(filename) {
            if (!confirm(`Delete ${filename}?`)) return;
            
            try {
                await fetch(`/delete/${filename}`, { method: 'DELETE' });
                document.querySelector(`[data-filename="${filename}"]`).remove();
            } catch (error) {
                this.displayError(error.message);
            }
        },
        
        displayError(message) {
            const errorLine = document.createElement('div');
            errorLine.className = 'history-line error';
            errorLine.textContent = `Error: ${message}`;
            this.history.appendChild(errorLine);
            this.history.scrollTop = this.history.scrollHeight;
        },
        
        resizeTerminal() {
            const terminalHeight = this.history.offsetHeight;
            const lineHeight = 18; // px
            this.history.style.maxHeight = `${Math.floor(terminalHeight / lineHeight) * lineHeight}px`;
        }
    };
    
    terminal.init();
});