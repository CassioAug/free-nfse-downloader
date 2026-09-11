#!/usr/bin/env python3
# free-nfse-downloader
# Copyright (C) 2026 Cassio Soares
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# -*- coding: utf-8 -*-

import os
import sys

# Reconfiguração segura de stream para Windows/consoles legados
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Suporte a Tk embutido no .venv (Linux) se o sistema não possuir tk instalado
if sys.platform.startswith("linux") and "TK_LIBRARY" not in os.environ:
    _venv_lib = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "lib")
    if os.path.exists(os.path.join(_venv_lib, "libtk8.6.so")):
        try:
            import _tkinter  # noqa: F401
        except ImportError:
            if "_TK_LOCAL_REEXEC" not in os.environ and sys.argv and sys.argv[0] != "-c":
                _env = os.environ.copy()
                _env["_TK_LOCAL_REEXEC"] = "1"
                _env["LD_LIBRARY_PATH"] = f"{_venv_lib}:{_env.get('LD_LIBRARY_PATH', '')}"
                _env["TK_LIBRARY"] = os.path.join(_venv_lib, "tk8.6")
                os.execve(sys.executable, [sys.executable] + sys.argv, _env)

import re
import threading
import subprocess
import shutil
import webbrowser
import updater
from version import __version__

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SRC_DIR)

def format_date_text(text, is_backspace=False):
    """
    Formata string de data para o padrão DD/MM/YYYY.
    Extrai dígitos e adiciona as barras conforme o usuário digita.
    """
    if not text:
        return ""
    digits = re.sub(r'\D', '', str(text))[:8]
    if is_backspace:
        if len(digits) <= 2:
            return digits
        elif len(digits) <= 4:
            return f"{digits[:2]}/{digits[2:]}"
        else:
            return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"
    else:
        if len(digits) == 2:
            return f"{digits}/"
        elif len(digits) == 4:
            return f"{digits[:2]}/{digits[2:4]}/"
        elif len(digits) < 2:
            return digits
        elif len(digits) < 4:
            return f"{digits[:2]}/{digits[2:]}"
        else:
            return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
    import customtkinter as ctk
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    _AppBase = ctk.CTk
    _ToplevelBase = ctk.CTkToplevel
except Exception:
    tk = None
    filedialog = messagebox = ctk = None
    _AppBase = object
    _ToplevelBase = object


class App(_AppBase):
    def __init__(self):
        if ctk is None:
            raise RuntimeError("Tkinter e CustomTkinter são necessários para executar a interface gráfica.")
        super().__init__()

        self.title(f"Free NFS-e Downloader v{__version__}")
        self.geometry("900x700")

        self.update_info = None
        self.banner_frame = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Linha do banner de atualização
        self.grid_rowconfigure(1, weight=1)  # Linha principal das abas
        self.grid_rowconfigure(2, weight=0)  # Linha da caixa de logs

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=20, pady=(10, 10), sticky="nsew")

        self.tab_download = self.tabview.add("Download NFS-e")
        self.tab_convert_pfx = self.tabview.add("Converter PFX/P12")
        self.tab_organize = self.tabview.add("Organizar NFS-e")
        self.tab_xml_pdf = self.tabview.add("XML para PDF")
        self.tab_about = self.tabview.add("Sobre")

        self.setup_download_tab()
        self.setup_convert_pfx_tab()
        self.setup_organize_tab()
        self.setup_xml_pdf_tab()
        self.setup_about_tab()

        self.log_box = ctk.CTkTextbox(self, height=170)
        self.log_box.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.log_box.configure(state="disabled")

        # Inicia checagem não-bloqueante de atualizações no GitHub
        threading.Thread(target=self._check_updates_background, daemon=True).start()

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.configure(state="disabled")

    def run_command_interactive(self, cmd, inputs, success_msg, error_msg):
        def task():
            self.log(f"Executando...\n")
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                env["PYTHONUNBUFFERED"] = "1"
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    bufsize=1,
                    universal_newlines=True
                )

                if inputs:
                    for inp in inputs:
                        process.stdin.write(inp + "\n")
                    process.stdin.flush()

                for line in process.stdout:
                    self.log(line.strip())

                process.wait()

                if process.returncode == 0:
                    self.log(f"\n--- {success_msg} ---")
                else:
                    self.log(f"\n--- {error_msg} (Código: {process.returncode}) ---")
            except Exception as e:
                self.log(f"\nErro inesperado: {str(e)}")
            finally:
                self.on_command_finish()

        self.btn_start_download.configure(state="disabled")
        threading.Thread(target=task, daemon=True).start()

    def run_command(self, cmd, success_msg="Concluído.", error_msg="Erro."):
        def task():
            self.log(f"Executando...\n")
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                env["PYTHONUNBUFFERED"] = "1"
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    bufsize=1,
                    universal_newlines=True
                )

                for line in process.stdout:
                    self.log(line.strip())

                process.wait()

                if process.returncode == 0:
                    self.log(f"\n--- {success_msg} ---")
                else:
                    self.log(f"\n--- {error_msg} (Código: {process.returncode}) ---")
            except Exception as e:
                self.log(f"\nErro inesperado: {str(e)}")
            finally:
                self.on_command_finish()

        # Disable all action buttons
        self.btn_start_download.configure(state="disabled")
        self.btn_convert_pfx.configure(state="disabled")
        self.btn_organize.configure(state="disabled")
        self.btn_convert_xml.configure(state="disabled")
        threading.Thread(target=task, daemon=True).start()

    def on_command_finish(self):
        self.btn_start_download.configure(state="normal")
        self.btn_convert_pfx.configure(state="normal")
        self.btn_organize.configure(state="normal")
        self.btn_convert_xml.configure(state="normal")

    def _on_date_key_release(self, entry, event=None):
        # Ignora teclas de navegação, modificadores e comandos de sistema
        if event and event.keysym in (
            "Left", "Right", "Up", "Down", "Home", "End",
            "Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Return", "Escape"
        ):
            return

        is_backspace = bool(event and event.keysym in ("BackSpace", "Delete"))
        current = entry.get()

        try:
            cursor_pos = entry.index(tk.INSERT)
        except Exception:
            cursor_pos = len(current)

        digits_before = len(re.sub(r'\D', '', current[:cursor_pos]))
        formatted = format_date_text(current, is_backspace=is_backspace)

        if current != formatted:
            entry.delete(0, tk.END)
            entry.insert(0, formatted)

            # Recalcula a nova posição do cursor mantendo o ponto de digitação correto
            if digits_before == 0:
                new_pos = 0
            else:
                count = 0
                new_pos = len(formatted)
                for idx, ch in enumerate(formatted):
                    if ch.isdigit():
                        count += 1
                        if count == digits_before:
                            new_pos = idx + 1
                            if not is_backspace and new_pos < len(formatted) and formatted[new_pos] == '/':
                                new_pos += 1
                            break
            try:
                entry.icursor(new_pos)
            except Exception:
                pass

    def _on_date_focus_out(self, entry, event=None):
        current = entry.get().strip()
        if not current:
            return
        formatted = format_date_text(current, is_backspace=True)
        if current != formatted:
            entry.delete(0, tk.END)
            entry.insert(0, formatted)

    def setup_download_tab(self):
        frame = ctk.CTkFrame(self.tab_download)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Description header
        ctk.CTkLabel(
            frame,
            text="Consulta e download automatizado de NFS-e diretamente do Ambiente de Dados Nacional (ADN) com geração de DANFSE em PDF.",
            text_color="gray",
            wraplength=750,
            justify="left"
        ).grid(row=0, column=0, columnspan=3, padx=10, pady=(2, 6), sticky="w")

        # Certificate Type
        self.cert_type_var = tk.StringVar(value="1")

        ctk.CTkLabel(frame, text="Tipo de Certificado:").grid(row=1, column=0, padx=10, pady=4, sticky="w")

        radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
        radio_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        self.rb_pem = ctk.CTkRadioButton(radio_frame, text="Arquivo PEM (A1)", variable=self.cert_type_var, value="1", command=self.update_download_ui)
        self.rb_pem.pack(side="left", padx=(0, 20))
        self.rb_a3 = ctk.CTkRadioButton(radio_frame, text="Token USB (A3)", variable=self.cert_type_var, value="2", command=self.update_download_ui)
        self.rb_a3.pack(side="left")

        self.lbl_cert_desc = ctk.CTkLabel(frame, text="", text_color="gray", font=("", 11), wraplength=700, justify="left")
        self.lbl_cert_desc.grid(row=2, column=1, columnspan=2, padx=10, pady=(0, 4), sticky="w")

        # Certificate Selection (PEM only or A3 index)
        self.lbl_cert = ctk.CTkLabel(frame, text="Certificado PEM:")
        self.lbl_cert.grid(row=3, column=0, padx=10, pady=4, sticky="w")

        self.cert_entry = ctk.CTkEntry(frame, placeholder_text="Será buscado em ./certificados")
        self.cert_entry.grid(row=3, column=1, padx=10, pady=4, sticky="ew")

        # A3 Index
        self.lbl_a3_index = ctk.CTkLabel(frame, text="Índice do Token A3:")
        self.a3_index_entry = ctk.CTkEntry(frame, placeholder_text="1")

        # CNPJ
        ctk.CTkLabel(frame, text="CNPJ (14 dígitos):").grid(row=4, column=0, padx=10, pady=4, sticky="w")
        self.cnpj_entry = ctk.CTkEntry(frame, placeholder_text="Deixe vazio para automático")
        self.cnpj_entry.grid(row=4, column=1, columnspan=2, padx=10, pady=4, sticky="ew")

        # Start Date
        ctk.CTkLabel(frame, text="Data Inicial (DD/MM/YYYY):").grid(row=5, column=0, padx=10, pady=4, sticky="w")
        self.start_date_entry = ctk.CTkEntry(frame, placeholder_text="Ex: 01/01/2026", width=180)
        self.start_date_entry.grid(row=5, column=1, padx=10, pady=4, sticky="w")
        self.start_date_entry.bind("<KeyRelease>", lambda e: self._on_date_key_release(self.start_date_entry, e))
        self.start_date_entry.bind("<FocusOut>", lambda e: self._on_date_focus_out(self.start_date_entry, e))

        # End Date
        ctk.CTkLabel(frame, text="Data Final (DD/MM/YYYY):").grid(row=6, column=0, padx=10, pady=4, sticky="w")
        self.end_date_entry = ctk.CTkEntry(frame, placeholder_text="Ex: 31/01/2026 (Deixe vazio para hoje)", width=280)
        self.end_date_entry.grid(row=6, column=1, padx=10, pady=4, sticky="w")
        self.end_date_entry.bind("<KeyRelease>", lambda e: self._on_date_key_release(self.end_date_entry, e))
        self.end_date_entry.bind("<FocusOut>", lambda e: self._on_date_focus_out(self.end_date_entry, e))

        # Ignore NSU Cache Checkbox
        self.ignore_cache_var = tk.BooleanVar(value=False)
        self.chk_ignore_cache = ctk.CTkCheckBox(frame, text="Ignorar cache NSU (forçar busca ampla)", variable=self.ignore_cache_var)
        self.chk_ignore_cache.grid(row=7, column=0, columnspan=2, padx=10, pady=(4, 0), sticky="w")

        ctk.CTkLabel(
            frame,
            text="Desconsidera o índice local de NSU e consulta a API desde o primeiro NSU disponível.",
            text_color="gray",
            font=("", 11)
        ).grid(row=8, column=0, columnspan=2, padx=36, pady=(0, 6), sticky="w")

        # Start Button
        self.btn_start_download = ctk.CTkButton(frame, text="Iniciar Download", command=self.start_download)
        self.btn_start_download.grid(row=9, column=0, columnspan=3, pady=10)

        # We also need dummy buttons for other tabs so they can be disabled initially
        self.btn_convert_pfx = ctk.CTkButton(self.tab_convert_pfx, text="")
        self.btn_organize = ctk.CTkButton(self.tab_organize, text="")
        self.btn_convert_xml = ctk.CTkButton(self.tab_xml_pdf, text="")

        self.update_download_ui()

    def update_download_ui(self):
        if self.cert_type_var.get() == "1":
            self.lbl_cert_desc.configure(text="Autenticação mTLS direta e rápida via certificados .pem salvos na pasta certificados/.")
            self.lbl_cert.grid(row=3, column=0, padx=10, pady=4, sticky="w")
            self.cert_entry.grid(row=3, column=1, padx=10, pady=4, sticky="ew")

            self.lbl_a3_index.grid_remove()
            self.a3_index_entry.grid_remove()
        else:
            self.lbl_cert_desc.configure(text="Autenticação via token/cartão físico no Windows Certificate Store com navegador integrado.")
            self.lbl_cert.grid_remove()
            self.cert_entry.grid_remove()

            self.lbl_a3_index.grid(row=3, column=0, padx=10, pady=4, sticky="w")
            self.a3_index_entry.grid(row=3, column=1, padx=10, pady=4, sticky="ew")

    def start_download(self):
        cert_type = self.cert_type_var.get()
        start_date = format_date_text(self.start_date_entry.get().strip())
        raw_end = self.end_date_entry.get().strip()
        end_date = format_date_text(raw_end) if raw_end else ""
        cnpj = self.cnpj_entry.get().strip()

        if not start_date:
            messagebox.showerror("Erro", "A data inicial é obrigatória.")
            return

        inputs = []
        inputs.append(cert_type)

        if cert_type == "1": # PEM
            cert_name = self.cert_entry.get().strip()
            # If user specified something, we might need to select it, but download_nfse lists files in ./certificados
            # If there's multiple, it asks for index.
            cert_dir = os.path.join(BASE_DIR, "certificados")
            if os.path.exists(cert_dir):
                files = [f for f in os.listdir(cert_dir) if f.endswith(".pem")]
                if len(files) > 1:
                    pem_name = self.cert_entry.get().strip()
                    if not pem_name:
                        inputs.append("1")
                    elif pem_name.isdigit():
                        inputs.append(pem_name)
                    else:
                        try:
                            idx = files.index(pem_name) + 1
                            inputs.append(str(idx))
                        except ValueError:
                            inputs.append("1")
                elif len(files) == 1:
                    pass
                else:
                    messagebox.showerror("Erro", "Nenhum arquivo .pem encontrado em ./certificados")
                    return
            else:
                messagebox.showerror("Erro", "Pasta ./certificados não encontrada")
                return
        else: # A3
            needs_a3_index = True
            try:
                import cert_handler
                token_certs = cert_handler.list_token_certs()
                if len(token_certs) <= 1:
                    needs_a3_index = False
            except Exception:
                pass

            if needs_a3_index:
                a3_idx = self.a3_index_entry.get().strip()
                if not a3_idx:
                    a3_idx = "1"
                inputs.append(a3_idx)

        inputs.append(start_date)
        if end_date:
            inputs.append(end_date)
        else:
            inputs.append("") # Deixa vazio para pegar a data de hoje

        cmd = [sys.executable, os.path.join(SRC_DIR, "download_nfse.py")]
        if self.ignore_cache_var.get():
            cmd.append("--ignorar-cache")

        self.log_box.delete("0.0", "end")
        self.run_command_interactive(
            cmd,
            inputs,
            "Download Finalizado.",
            "Erro no Download."
        )


    def setup_convert_pfx_tab(self):
        frame = ctk.CTkFrame(self.tab_convert_pfx)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Description header
        ctk.CTkLabel(
            frame,
            text="Converte certificados digitais A1 (.pfx ou .p12) para arquivos .pem em ./certificados, formato necessário para autenticação mTLS.",
            text_color="gray",
            wraplength=750,
            justify="left"
        ).grid(row=0, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="w")

        # PFX Path
        ctk.CTkLabel(frame, text="Arquivo PFX/P12:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.pfx_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./certificados/meu_cert.pfx")
        self.pfx_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_pfx = ctk.CTkButton(frame, text="Procurar...", command=self.browse_pfx)
        self.btn_browse_pfx.grid(row=1, column=2, padx=10, pady=10)

        # Password
        ctk.CTkLabel(frame, text="Senha do Certificado:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.pfx_pass_entry = ctk.CTkEntry(frame, show="*")
        self.pfx_pass_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # PEM Output Path (Optional)
        ctk.CTkLabel(frame, text="Arquivo PEM (Saída):").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.pem_out_entry = ctk.CTkEntry(frame, placeholder_text="Opcional. Padrão: mesmo nome na pasta ./certificados")
        self.pem_out_entry.grid(row=3, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Start Button
        self.btn_convert_pfx = ctk.CTkButton(frame, text="Converter PFX -> PEM", command=self.start_convert_pfx)
        self.btn_convert_pfx.grid(row=4, column=0, columnspan=3, pady=20)

    def browse_pfx(self):
        filename = filedialog.askopenfilename(title="Selecione o arquivo PFX/P12", filetypes=(("PFX/P12 files", "*.pfx *.p12"), ("All files", "*.*")))
        if filename:
            self.pfx_entry.delete(0, tk.END)
            self.pfx_entry.insert(0, filename)

    def start_convert_pfx(self):
        pfx_path = self.pfx_entry.get().strip()
        pfx_pass = self.pfx_pass_entry.get()
        pem_out = self.pem_out_entry.get().strip()

        if not pfx_path:
            messagebox.showerror("Erro", "O caminho do arquivo PFX/P12 é obrigatório.")
            return

        cmd = [sys.executable, os.path.join(SRC_DIR, "convert_pfx.py"), pfx_path, pfx_pass]
        if pem_out:
            cmd.append(pem_out)
        else:
            base_name = os.path.basename(pfx_path)
            default_pem = os.path.join(os.path.join(BASE_DIR, "certificados"), os.path.splitext(base_name)[0] + ".pem")
            cmd.append(default_pem)

        self.log_box.delete("0.0", "end")
        self.run_command(cmd, "Conversão Finalizada.", "Erro na Conversão.")



    def setup_organize_tab(self):
        frame = ctk.CTkFrame(self.tab_organize)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Description header
        ctk.CTkLabel(
            frame,
            text="Classifica arquivos XML locais em subpastas 'prestados' e 'tomados' comparando o CNPJ da empresa com os participantes da nota.",
            text_color="gray",
            wraplength=750,
            justify="left"
        ).grid(row=0, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="w")

        # XML Directory
        ctk.CTkLabel(frame, text="Pasta dos XMLs:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.org_dir_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./notas_fiscais/12345678000199")
        self.org_dir_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_org = ctk.CTkButton(frame, text="Procurar...", command=self.browse_org)
        self.btn_browse_org.grid(row=1, column=2, padx=10, pady=10)

        # CNPJ
        ctk.CTkLabel(frame, text="CNPJ (14 dígitos):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.org_cnpj_entry = ctk.CTkEntry(frame, placeholder_text="Apenas números")
        self.org_cnpj_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Start Button
        self.btn_organize = ctk.CTkButton(frame, text="Organizar Notas", command=self.start_organize)
        self.btn_organize.grid(row=3, column=0, columnspan=3, pady=20)

    def browse_org(self):
        directory = filedialog.askdirectory(title="Selecione a pasta dos XMLs")
        if directory:
            self.org_dir_entry.delete(0, tk.END)
            self.org_dir_entry.insert(0, directory)

    def start_organize(self):
        directory = self.org_dir_entry.get().strip()
        cnpj = self.org_cnpj_entry.get().strip()

        if not directory or not cnpj:
            messagebox.showerror("Erro", "O diretório e o CNPJ são obrigatórios.")
            return

        cmd = [sys.executable, os.path.join(SRC_DIR, "organize_nfse.py"), "--dir", directory, "--cnpj", cnpj]

        self.log_box.delete("0.0", "end")
        self.run_command(cmd, "Organização Finalizada.", "Erro na Organização.")



    def setup_xml_pdf_tab(self):
        frame = ctk.CTkFrame(self.tab_xml_pdf)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Description header
        ctk.CTkLabel(
            frame,
            text="Converte arquivos XML de NFS-e salvos no disco em relatórios visuais DANFSE (PDF) em lote, sem consultar a internet.",
            text_color="gray",
            wraplength=750,
            justify="left"
        ).grid(row=0, column=0, columnspan=3, padx=10, pady=(5, 10), sticky="w")

        # Input Path (File or Directory)
        ctk.CTkLabel(frame, text="XML ou Pasta:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.xml_input_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./notas_fiscais")
        self.xml_input_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_xml = ctk.CTkButton(frame, text="Procurar...", command=self.browse_xml)
        self.btn_browse_xml.grid(row=1, column=2, padx=10, pady=10)

        # Output Path (Optional)
        ctk.CTkLabel(frame, text="Pasta Destino (Opcional):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.pdf_out_entry = ctk.CTkEntry(frame, placeholder_text="Deixe vazio para mesma pasta do XML")
        self.pdf_out_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_pdf_out = ctk.CTkButton(frame, text="Procurar...", command=self.browse_pdf_out)
        self.btn_browse_pdf_out.grid(row=2, column=2, padx=10, pady=10)

        # Force overwrite
        self.force_var = tk.BooleanVar(value=False)
        self.chk_force = ctk.CTkCheckBox(frame, text="Forçar conversão (Sobrescrever PDFs existentes)", variable=self.force_var)
        self.chk_force.grid(row=3, column=1, columnspan=2, padx=10, pady=10, sticky="w")

        # Start Button
        self.btn_convert_xml = ctk.CTkButton(frame, text="Converter XML -> PDF", command=self.start_convert_xml)
        self.btn_convert_xml.grid(row=4, column=0, columnspan=3, pady=20)

    def browse_xml(self):
        path = filedialog.askopenfilename(title="Selecione o XML", filetypes=(("XML files", "*.xml"), ("All files", "*.*")))
        if not path:
            path = filedialog.askdirectory(title="Ou selecione a pasta")
        if path:
            self.xml_input_entry.delete(0, tk.END)
            self.xml_input_entry.insert(0, path)

    def browse_pdf_out(self):
        directory = filedialog.askdirectory(title="Selecione a pasta destino")
        if directory:
            self.pdf_out_entry.delete(0, tk.END)
            self.pdf_out_entry.insert(0, directory)

    def start_convert_xml(self):
        input_path = self.xml_input_entry.get().strip()
        out_path = self.pdf_out_entry.get().strip()
        force = self.force_var.get()

        cmd = [sys.executable, os.path.join(SRC_DIR, "xml_to_pdf.py")]

        if input_path:
            cmd.append(input_path)

        if out_path:
            cmd.extend(["-o", out_path])

        if force:
            cmd.append("-f")

        self.log_box.delete("0.0", "end")
        self.run_command(cmd, "Conversão Finalizada.", "Erro na Conversão.")

    def setup_about_tab(self):
        frame = ctk.CTkFrame(self.tab_about)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")

        lbl_title = ctk.CTkLabel(
            container,
            text="Free NFS-e Downloader",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        lbl_title.pack(pady=(0, 5))

        lbl_version = ctk.CTkLabel(
            container,
            text=f"Versão {__version__}",
            font=ctk.CTkFont(size=14, slant="italic")
        )
        lbl_version.pack(pady=(0, 10))

        # Seção de Atualização
        self.update_card = ctk.CTkFrame(container, fg_color=("gray85", "gray17"), corner_radius=8)
        self.update_card.pack(pady=(0, 15), padx=20, fill="x")

        self.lbl_update_status = ctk.CTkLabel(
            self.update_card,
            text="Verificação automática em segundo plano ativada.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.lbl_update_status.pack(pady=(8, 4), padx=15)

        self.btn_check_update = ctk.CTkButton(
            self.update_card,
            text="🔍 Verificar Atualizações",
            command=self.manual_check_updates,
            width=220,
            height=32
        )
        self.btn_check_update.pack(pady=(0, 8), padx=15)

        lbl_desc = ctk.CTkLabel(
            container,
            text="Automação, sincronização e download em lote de Notas Fiscais de Serviços\nEletrônicas (NFS-e) diretamente da API do Ambiente de Dados Nacional.",
            justify="center",
            font=ctk.CTkFont(size=13)
        )
        lbl_desc.pack(pady=(0, 18))

        lbl_author = ctk.CTkLabel(
            container,
            text="Desenvolvido por: Cássio Augusto Couto Soares (CassioAug)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_author.pack(pady=(0, 10))

        btn_github = ctk.CTkButton(
            container,
            text="🌐 Abrir Repositório no GitHub",
            command=lambda: webbrowser.open("https://github.com/CassioAug/free-nfse-downloader"),
            width=260,
            height=36
        )
        btn_github.pack(pady=(0, 18))

        lbl_license = ctk.CTkLabel(
            container,
            text="Licença: GNU General Public License v3.0 (GPLv3)",
            font=ctk.CTkFont(size=12, slant="italic")
        )
        lbl_license.pack(pady=(0, 5))

    def _check_updates_background(self):
        try:
            info = updater.check_for_updates(__version__, timeout=4)
            if info:
                self.update_info = info
                self.after(0, lambda: self._show_update_notification(info))
        except Exception:
            pass

    def _show_update_notification(self, info):
        if hasattr(self, "lbl_update_status") and self.lbl_update_status:
            self.lbl_update_status.configure(
                text=f"✨ Nova versão {info['tag_name']} disponível!",
                text_color="#28a745"
            )
        if hasattr(self, "btn_check_update") and self.btn_check_update:
            self.btn_check_update.configure(
                text=f"🚀 Atualizar para {info['tag_name']}",
                fg_color="#28a745",
                hover_color="#218838",
                command=lambda: self.open_update_dialog(info)
            )

        if self.banner_frame is None and ctk is not None:
            self.banner_frame = ctk.CTkFrame(self, fg_color=("#D4EDDA", "#1E4620"), corner_radius=6)
            self.banner_frame.grid(row=0, column=0, padx=20, pady=(10, 0), sticky="ew")

            lbl_banner = ctk.CTkLabel(
                self.banner_frame,
                text=f"🎉 Nova versão do Free NFS-e Downloader disponível ({info['tag_name']})!",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#155724", "#D4EDDA")
            )
            lbl_banner.pack(side="left", padx=15, pady=8)

            btn_update_banner = ctk.CTkButton(
                self.banner_frame,
                text="Ver e Atualizar",
                font=ctk.CTkFont(size=12),
                height=26,
                fg_color="#28a745",
                hover_color="#218838",
                command=lambda: self.open_update_dialog(info)
            )
            btn_update_banner.pack(side="left", padx=10, pady=8)

            btn_close_banner = ctk.CTkButton(
                self.banner_frame,
                text="✕",
                width=26,
                height=26,
                font=ctk.CTkFont(size=12),
                fg_color="transparent",
                text_color=("#155724", "#D4EDDA"),
                hover_color=("#C3E6CB", "#295B2B"),
                command=self.dismiss_banner
            )
            btn_close_banner.pack(side="right", padx=10, pady=8)

    def dismiss_banner(self):
        if self.banner_frame:
            self.banner_frame.grid_forget()

    def open_update_dialog(self, info=None):
        target_info = info or self.update_info
        if target_info:
            UpdateDialog(self, target_info)

    def manual_check_updates(self):
        self.btn_check_update.configure(state="disabled", text="Verificando...")
        self.lbl_update_status.configure(text="Consultando lançamentos no GitHub...", text_color="gray")

        def worker():
            try:
                info = updater.check_for_updates(__version__, timeout=6)
            except Exception:
                info = None
            self.after(0, lambda: self._on_manual_check_done(info))

        threading.Thread(target=worker, daemon=True).start()

    def _on_manual_check_done(self, info):
        self.btn_check_update.configure(state="normal", text="🔍 Verificar Atualizações")
        if info:
            self.update_info = info
            self._show_update_notification(info)
            self.open_update_dialog(info)
        else:
            self.lbl_update_status.configure(
                text=f"Você já está utilizando a versão mais recente (v{__version__}).",
                text_color="gray"
            )


class UpdateDialog(_ToplevelBase):
    """
    Diálogo modal moderno para exibição de release notes, download e atualização com 1 clique.
    """
    def __init__(self, master, info):
        if ctk is None:
            return
        super().__init__(master)
        self.master = master
        self.info = info

        self.title("Atualização - Free NFS-e Downloader")
        self.geometry("560x520")
        self.minsize(500, 440)

        try:
            self.transient(master)
            self.grab_set()
        except Exception:
            pass

        self._setup_ui()

    def _setup_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho com versão
        lbl_head = ctk.CTkLabel(
            container,
            text=f"Nova Versão {self.info.get('tag_name', '')} Disponível!",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        lbl_head.pack(pady=(0, 4), anchor="w")

        lbl_sub = ctk.CTkLabel(
            container,
            text=self.info.get("title") or "Atualização oficial do Free NFS-e Downloader",
            font=ctk.CTkFont(size=13, slant="italic"),
            text_color="gray"
        )
        lbl_sub.pack(pady=(0, 10), anchor="w")

        # Caixa de Release Notes
        lbl_notes_title = ctk.CTkLabel(
            container,
            text="O que há de novo nesta versão:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_notes_title.pack(anchor="w", pady=(4, 3))

        self.txt_notes = ctk.CTkTextbox(container, height=180, font=ctk.CTkFont(size=12))
        self.txt_notes.pack(fill="both", expand=True, pady=(0, 10))
        self.txt_notes.insert("0.0", self.info.get("body", "Sem notas adicionais."))
        self.txt_notes.configure(state="disabled")

        # Garantia de segurança de dados fiscais
        lbl_security = ctk.CTkLabel(
            container,
            text="[OK] Seus certificados (.pem/.pfx) e notas fiscais já baixadas não serão afetados.",
            font=ctk.CTkFont(size=11),
            text_color="#28a745"
        )
        lbl_security.pack(anchor="w", pady=(0, 10))

        # Barra de progresso do download
        self.progress_bar = ctk.CTkProgressBar(container, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.pack_forget()

        self.lbl_progress = ctk.CTkLabel(
            container,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.lbl_progress.pack(anchor="w", pady=(0, 10))
        self.lbl_progress.pack_forget()

        # Botões de Ação
        self.actions_frame = ctk.CTkFrame(container, fg_color="transparent")
        self.actions_frame.pack(fill="x", pady=(5, 0))

        self.btn_update = ctk.CTkButton(
            self.actions_frame,
            text="🚀 Atualizar Agora",
            command=self.start_download,
            fg_color="#28a745",
            hover_color="#218838",
            height=36
        )
        self.btn_update.pack(side="left", padx=(0, 10))

        self.btn_browser = ctk.CTkButton(
            self.actions_frame,
            text="🌐 Ver no GitHub",
            command=lambda: webbrowser.open(self.info.get("html_url", "")),
            height=36,
            fg_color=("gray75", "gray25"),
            text_color=("black", "white"),
            hover_color=("gray65", "gray35")
        )
        self.btn_browser.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            self.actions_frame,
            text="Lembrar Mais Tarde",
            command=self.destroy,
            fg_color="transparent",
            border_width=1,
            height=36
        )
        self.btn_cancel.pack(side="right")

    def start_download(self):
        zip_url = self.info.get("zip_url")
        if not zip_url:
            webbrowser.open(self.info.get("html_url", ""))
            self.destroy()
            return

        self.btn_update.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        self.btn_browser.configure(state="disabled")

        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.lbl_progress.pack(anchor="w", pady=(0, 10))
        self.lbl_progress.configure(text="Conectando ao servidor do GitHub...")

        def worker():
            try:
                def on_progress(pct, downloaded, total):
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    text = f"Baixando pacote: {mb_down:.1f} MB de {mb_total:.1f} MB ({int(pct * 100)}%)"
                    self.after(0, lambda: self._update_progress_ui(pct, text))

                staging_dir = updater.download_and_extract_update(zip_url, progress_callback=on_progress)
                self.after(0, lambda: self._on_download_complete(staging_dir))
            except Exception as e:
                self.after(0, lambda: self._on_download_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_ui(self, pct, text):
        self.progress_bar.set(pct)
        self.lbl_progress.configure(text=text)

    def _on_download_complete(self, staging_dir):
        self.progress_bar.set(1.0)
        self.lbl_progress.configure(
            text="[OK] Download concluído! Reiniciando aplicação...",
            text_color="#28a745"
        )
        try:
            updater.trigger_update_process(staging_dir)
        except Exception as e:
            self._on_download_error(f"Erro ao disparar atualizador: {e}")
            return

        self.after(1200, self.master.destroy)

    def _on_download_error(self, error_msg):
        self.lbl_progress.configure(
            text=f"[ERRO] {error_msg}",
            text_color="red"
        )
        self.btn_update.configure(state="normal", text="Tentar Novamente")
        self.btn_cancel.configure(state="normal")
        self.btn_browser.configure(state="normal")


if __name__ == "__main__":
    app = App()
    app.mainloop()
