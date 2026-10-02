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

import csv
from datetime import datetime
try:
    import database
    HAS_DATABASE = True
except Exception:
    HAS_DATABASE = False

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import customtkinter as ctk
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    _AppBase = ctk.CTk
    _ToplevelBase = ctk.CTkToplevel
except Exception:
    tk = None
    filedialog = messagebox = ctk = ttk = None
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
        self.active_process = None

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
        self.tab_database = self.tabview.add("Banco de Dados")
        self.tab_about = self.tabview.add("Sobre")

        self.setup_download_tab()
        self.setup_convert_pfx_tab()
        self.setup_organize_tab()
        self.setup_xml_pdf_tab()
        self.setup_database_tab()
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

    def cancel_active_process(self):
        """Interrompe e encerra o processo em execução a pedido do usuário"""
        if self.active_process:
            try:
                self.log("\n[Aviso] Interrompendo operação a pedido do usuário...")
                self.active_process.terminate()
                time.sleep(0.3)
                if self.active_process.poll() is None:
                    self.active_process.kill()
            except Exception as e:
                self.log(f"\nErro ao cancelar processo: {e}")
            finally:
                self.on_command_finish()

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
                self.active_process = process

                if inputs:
                    for inp in inputs:
                        process.stdin.write(inp + "\n")
                    process.stdin.flush()

                for line in process.stdout:
                    self.log(line.strip())

                process.wait()

                if process.returncode == 0:
                    self.log(f"\n--- {success_msg} ---")
                elif process.returncode in (-15, -9, 15, 1):
                    self.log(f"\n--- Operação finalizada / cancelada (Código: {process.returncode}) ---")
                else:
                    self.log(f"\n--- {error_msg} (Código: {process.returncode}) ---")
            except Exception as e:
                self.log(f"\nErro inesperado: {str(e)}")
            finally:
                self.on_command_finish()

        self.btn_start_download.configure(state="disabled")
        if hasattr(self, "btn_cancel_op") and self.btn_cancel_op:
            self.btn_cancel_op.configure(state="normal")
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
                self.active_process = process

                for line in process.stdout:
                    self.log(line.strip())

                process.wait()

                if process.returncode == 0:
                    self.log(f"\n--- {success_msg} ---")
                elif process.returncode in (-15, -9, 15, 1):
                    self.log(f"\n--- Operação finalizada / cancelada (Código: {process.returncode}) ---")
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
        if hasattr(self, "btn_cancel_op") and self.btn_cancel_op:
            self.btn_cancel_op.configure(state="normal")
        threading.Thread(target=task, daemon=True).start()

    def on_command_finish(self):
        self.active_process = None
        self.btn_start_download.configure(state="normal")
        self.btn_convert_pfx.configure(state="normal")
        self.btn_organize.configure(state="normal")
        self.btn_convert_xml.configure(state="normal")
        if hasattr(self, "btn_cancel_op") and self.btn_cancel_op:
            self.btn_cancel_op.configure(state="disabled")

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

        # Action Buttons (Iniciar + Interromper)
        btn_action_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_action_frame.grid(row=9, column=0, columnspan=3, pady=10)

        self.btn_start_download = ctk.CTkButton(btn_action_frame, text="▶ Iniciar Download", width=160, height=34, command=self.start_download)
        self.btn_start_download.pack(side="left", padx=8)

        self.btn_cancel_op = ctk.CTkButton(
            btn_action_frame, text="🛑 Cancelar Operação", width=160, height=34,
            fg_color="#dc3545", hover_color="#c82333",
            state="disabled", command=self.cancel_active_process
        )
        self.btn_cancel_op.pack(side="left", padx=8)

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
        end_date = format_date_text(raw_end) if raw_end else datetime.today().strftime("%d/%m/%Y")
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
        inputs.append(end_date)

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

    def setup_database_tab(self):
        """Aba de Consulta, Métricas Financeiras e Gerenciamento do Banco SQLite"""
        self.tab_database.grid_columnconfigure(0, weight=1)
        self.tab_database.grid_rowconfigure(2, weight=1)

        # 1. Painel de Filtros
        filter_frame = ctk.CTkFrame(self.tab_database)
        filter_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        filter_frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1)

        # Linha 1 de filtros
        ctk.CTkLabel(filter_frame, text="CNPJ:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_cnpj = ctk.CTkEntry(filter_frame, placeholder_text="14 dígitos", width=120)
        self.db_filter_cnpj.grid(row=1, column=0, padx=5, pady=(0, 5), sticky="ew")

        ctk.CTkLabel(filter_frame, text="Tipo:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_tipo = ctk.CTkOptionMenu(filter_frame, values=["Todos", "prestado", "tomado"], width=100)
        self.db_filter_tipo.grid(row=1, column=1, padx=5, pady=(0, 5), sticky="ew")

        ctk.CTkLabel(filter_frame, text="Status:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_status = ctk.CTkOptionMenu(filter_frame, values=["Todos", "autorizada", "cancelada"], width=110)
        self.db_filter_status.grid(row=1, column=2, padx=5, pady=(0, 5), sticky="ew")

        ctk.CTkLabel(filter_frame, text="Data Inicial:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=3, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_dini = ctk.CTkEntry(filter_frame, placeholder_text="DD/MM/YYYY", width=100)
        self.db_filter_dini.grid(row=1, column=3, padx=5, pady=(0, 5), sticky="ew")
        self.db_filter_dini.bind("<KeyRelease>", lambda e: self._on_date_key_release(self.db_filter_dini, e))

        ctk.CTkLabel(filter_frame, text="Data Final:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=4, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_dfim = ctk.CTkEntry(filter_frame, placeholder_text="DD/MM/YYYY", width=100)
        self.db_filter_dfim.grid(row=1, column=4, padx=5, pady=(0, 5), sticky="ew")
        self.db_filter_dfim.bind("<KeyRelease>", lambda e: self._on_date_key_release(self.db_filter_dfim, e))

        ctk.CTkLabel(filter_frame, text="Busca / Texto:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=5, padx=5, pady=(5, 2), sticky="w")
        self.db_filter_search = ctk.CTkEntry(filter_frame, placeholder_text="Número, Nome, CNPJ...", width=140)
        self.db_filter_search.grid(row=1, column=5, padx=5, pady=(0, 5), sticky="ew")
        self.db_filter_search.bind("<Return>", lambda e: self.refresh_database_view())

        # Botões de Ação do Filtro
        btn_filter_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        btn_filter_frame.grid(row=2, column=0, columnspan=6, padx=5, pady=(2, 6), sticky="e")

        self.btn_db_filter = ctk.CTkButton(btn_filter_frame, text="🔎 Filtrar", width=90, height=28, command=self.refresh_database_view)
        self.btn_db_filter.pack(side="right", padx=5)

        self.btn_db_clear = ctk.CTkButton(
            btn_filter_frame, text="🧹 Limpar", width=80, height=28,
            fg_color=("gray75", "gray25"), text_color=("black", "white"),
            command=self._clear_db_filters
        )
        self.btn_db_clear.pack(side="right", padx=5)

        # 2. Card de Resumo Financeiro
        self.summary_frame = ctk.CTkFrame(self.tab_database, fg_color=("gray88", "gray18"), corner_radius=6)
        self.summary_frame.grid(row=1, column=0, padx=10, pady=(2, 5), sticky="ew")

        self.lbl_summary_text = ctk.CTkLabel(
            self.summary_frame,
            text="Carregando resumo financeiro...",
            font=ctk.CTkFont(size=12, weight="bold"),
            justify="center"
        )
        self.lbl_summary_text.pack(padx=10, pady=6)

        # 3. Tabela de Registros (Treeview)
        table_container = ctk.CTkFrame(self.tab_database)
        table_container.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        table_container.grid_columnconfigure(0, weight=1)
        table_container.grid_rowconfigure(0, weight=1)

        columns = ("emissao", "numero", "status", "tipo", "prestador", "tomador", "valor", "iss", "xml", "pdf")
        self.tree_notas = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="browse", height=10)

        self.tree_notas.heading("emissao", text="Emissão")
        self.tree_notas.heading("numero", text="Número")
        self.tree_notas.heading("status", text="Status")
        self.tree_notas.heading("tipo", text="Tipo")
        self.tree_notas.heading("prestador", text="Prestador")
        self.tree_notas.heading("tomador", text="Tomador")
        self.tree_notas.heading("valor", text="Valor (R$)")
        self.tree_notas.heading("iss", text="ISS (R$)")
        self.tree_notas.heading("xml", text="XML")
        self.tree_notas.heading("pdf", text="PDF")

        self.tree_notas.column("emissao", width=80, anchor="center")
        self.tree_notas.column("numero", width=70, anchor="center")
        self.tree_notas.column("status", width=85, anchor="center")
        self.tree_notas.column("tipo", width=65, anchor="center")
        self.tree_notas.column("prestador", width=160, anchor="w")
        self.tree_notas.column("tomador", width=160, anchor="w")
        self.tree_notas.column("valor", width=85, anchor="e")
        self.tree_notas.column("iss", width=75, anchor="e")
        self.tree_notas.column("xml", width=40, anchor="center")
        self.tree_notas.column("pdf", width=40, anchor="center")

        # Tags para estilização visual
        self.tree_notas.tag_configure("cancelada", foreground="#dc3545")
        self.tree_notas.tag_configure("autorizada", foreground="")

        tree_scroll_y = ttk.Scrollbar(table_container, orient="vertical", command=self.tree_notas.yview)
        self.tree_notas.configure(yscrollcommand=tree_scroll_y.set)

        self.tree_notas.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")

        self.tree_notas.bind("<Double-1>", lambda e: self.open_selected_pdf())

        # 4. Barra de Ações Inferior
        actions_bar = ctk.CTkFrame(self.tab_database, fg_color="transparent")
        actions_bar.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="ew")

        self.btn_open_xml = ctk.CTkButton(actions_bar, text="📄 Abrir XML", width=100, height=32, command=self.open_selected_xml)
        self.btn_open_xml.pack(side="left", padx=(0, 8))

        self.btn_open_pdf = ctk.CTkButton(actions_bar, text="📑 Abrir DANFSE (PDF)", width=140, height=32, command=self.open_selected_pdf)
        self.btn_open_pdf.pack(side="left", padx=(0, 8))

        self.btn_export_csv = ctk.CTkButton(
            actions_bar, text="📊 Exportar CSV", width=110, height=32,
            fg_color="#17a2b8", hover_color="#138496",
            command=self.export_database_csv
        )
        self.btn_export_csv.pack(side="left", padx=(0, 8))

        self.btn_sync_db = ctk.CTkButton(
            actions_bar, text="🔄 Importar / Sincronizar Arquivos Locais", width=220, height=32,
            fg_color="#28a745", hover_color="#218838",
            command=self.sync_local_files_to_db
        )
        self.btn_sync_db.pack(side="right", padx=0)

        # Mapa de dados em memória para a tabela {item_id: nota_dict}
        self._table_records = {}

        # Carrega os dados iniciais
        self.after(500, self.refresh_database_view)

    def _clear_db_filters(self):
        self.db_filter_cnpj.delete(0, tk.END)
        self.db_filter_tipo.set("Todos")
        self.db_filter_status.set("Todos")
        self.db_filter_dini.delete(0, tk.END)
        self.db_filter_dfim.delete(0, tk.END)
        self.db_filter_search.delete(0, tk.END)
        self.refresh_database_view()

    def refresh_database_view(self):
        if not HAS_DATABASE or not hasattr(self, "tree_notas"):
            return

        cnpj = self.db_filter_cnpj.get().strip()
        tipo_val = self.db_filter_tipo.get().strip()
        tipo = None if tipo_val == "Todos" else tipo_val

        status_val = self.db_filter_status.get().strip()
        status_param = None if status_val == "Todos" else status_val

        # Datas
        dini_str = self.db_filter_dini.get().strip()
        dfim_str = self.db_filter_dfim.get().strip()
        start_date = None
        end_date = None
        if len(re.sub(r'\D', '', dini_str)) == 8:
            try:
                start_date = datetime.strptime(dini_str, "%d/%m/%Y").date()
            except Exception:
                pass
        if len(re.sub(r'\D', '', dfim_str)) == 8:
            try:
                end_date = datetime.strptime(dfim_str, "%d/%m/%Y").date()
            except Exception:
                pass

        search = self.db_filter_search.get().strip() or None

        # Limpa tabela
        for item in self.tree_notas.get_children():
            self.tree_notas.delete(item)
        self._table_records.clear()

        # Consulta resumo financeiro
        try:
            summary = database.get_financial_summary(cnpj=cnpj or None, start_date=start_date, end_date=end_date)
            total_notas = summary.get("total_notas", 0) or 0
            total_canc = summary.get("total_canceladas", 0) or 0
            fat = summary.get("total_faturado", 0.0) or 0.0
            tom = summary.get("total_tomado_servico", 0.0) or 0.0
            iss = summary.get("total_iss", 0.0) or 0.0

            text_sum = (
                f"Total de Notas: {total_notas} (Canceladas: {total_canc})  |  "
                f"Faturado (Prestadas): R$ {fat:,.2f}  |  "
                f"Tomado: R$ {tom:,.2f}  |  "
                f"Total ISS: R$ {iss:,.2f}"
            ).replace(",", "X").replace(".", ",").replace("X", ".")
            self.lbl_summary_text.configure(text=text_sum)
        except Exception as e:
            self.lbl_summary_text.configure(text=f"Erro ao calcular resumo: {e}")

        # Consulta registros
        try:
            notas = database.query_notas(
                cnpj=cnpj or None,
                tipo=tipo,
                status=status_param,
                start_date=start_date,
                end_date=end_date,
                search_text=search,
                limit=500
            )
            for n in notas:
                dt_str = ""
                if n.get("data_emissao"):
                    try:
                        dt_obj = datetime.strptime(n["data_emissao"], "%Y-%m-%d")
                        dt_str = dt_obj.strftime("%d/%m/%Y")
                    except Exception:
                        dt_str = n["data_emissao"]

                status_raw = (n.get("status") or "autorizada").lower()
                status_display = "CANCELADA" if status_raw == "cancelada" else "Autorizada"
                tag_name = "cancelada" if status_raw == "cancelada" else "autorizada"

                val_serv = f"R$ {n.get('valor_servico', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                val_iss = f"R$ {n.get('valor_iss', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                tem_xml = "SIM" if n.get("caminho_xml") and os.path.isfile(n["caminho_xml"]) else "NÃO"
                tem_pdf = "SIM" if n.get("caminho_pdf") and os.path.isfile(n["caminho_pdf"]) else "NÃO"

                item_id = self.tree_notas.insert("", "end", values=(
                    dt_str,
                    n.get("numero_nfse") or "-",
                    status_display,
                    (n.get("tipo") or "-").capitalize(),
                    n.get("prestador_nome") or n.get("prestador_cnpj_cpf") or "-",
                    n.get("tomador_nome") or n.get("tomador_cnpj_cpf") or "-",
                    val_serv,
                    val_iss,
                    tem_xml,
                    tem_pdf
                ), tags=(tag_name,))
                self._table_records[item_id] = n
        except Exception as e:
            self.log(f"Erro ao consultar banco de dados: {e}")

    def _get_selected_nota(self):
        sel = self.tree_notas.selection()
        if not sel:
            messagebox.showwarning("Seleção", "Por favor, selecione uma nota na tabela.")
            return None
        return self._table_records.get(sel[0])

    def open_selected_xml(self):
        nota = self._get_selected_nota()
        if not nota:
            return
        caminho = nota.get("caminho_xml")
        if caminho and os.path.isfile(caminho):
            self._open_file(caminho)
        else:
            messagebox.showwarning("Arquivo Não Encontrado", f"O arquivo XML desta nota não foi encontrado em:\n{caminho or 'Nenhum caminho registrado'}")

    def open_selected_pdf(self):
        nota = self._get_selected_nota()
        if not nota:
            return
        caminho_pdf = nota.get("caminho_pdf")
        if caminho_pdf and os.path.isfile(caminho_pdf):
            self._open_file(caminho_pdf)
            return

        caminho_xml = nota.get("caminho_xml")
        if caminho_xml and os.path.isfile(caminho_xml):
            try:
                from xml_to_pdf import convert_single_xml
                if convert_single_xml(caminho_xml, overwrite=True):
                    base_pdf = os.path.splitext(caminho_xml)[0] + ".pdf"
                    if os.path.isfile(base_pdf):
                        self.refresh_database_view()
                        self._open_file(base_pdf)
                        return
            except Exception as e:
                messagebox.showerror("Erro ao Gerar PDF", f"Falha ao gerar DANFSE PDF: {e}")
                return

        messagebox.showwarning("PDF Não Encontrado", "O arquivo PDF correspondente não foi encontrado.")

    def _open_file(self, file_path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(os.path.abspath(file_path))
            elif sys.platform.startswith("darwin"):
                subprocess.Popen(["open", os.path.abspath(file_path)])
            else:
                subprocess.Popen(["xdg-open", os.path.abspath(file_path)])
        except Exception as e:
            messagebox.showerror("Erro ao Abrir", f"Não foi possível abrir o arquivo: {e}")

    def export_database_csv(self):
        if not HAS_DATABASE:
            return

        path = filedialog.asksaveasfilename(
            title="Salvar Relatório de Notas (CSV)",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
        )
        if not path:
            return

        try:
            cnpj = self.db_filter_cnpj.get().strip() or None
            tipo_val = self.db_filter_tipo.get().strip()
            tipo = None if tipo_val == "Todos" else tipo_val
            status_val = self.db_filter_status.get().strip()
            status_param = None if status_val == "Todos" else status_val

            dini_str = self.db_filter_dini.get().strip()
            dfim_str = self.db_filter_dfim.get().strip()
            start_date = None
            end_date = None
            if len(re.sub(r'\D', '', dini_str)) == 8:
                start_date = datetime.strptime(dini_str, "%d/%m/%Y").date()
            if len(re.sub(r'\D', '', dfim_str)) == 8:
                end_date = datetime.strptime(dfim_str, "%d/%m/%Y").date()
            search = self.db_filter_search.get().strip() or None

            notas = database.query_notas(
                cnpj=cnpj,
                tipo=tipo,
                status=status_param,
                start_date=start_date,
                end_date=end_date,
                search_text=search,
                limit=10000
            )

            if not notas:
                messagebox.showinfo("Exportar CSV", "Nenhuma nota encontrada com os filtros atuais.")
                return

            fieldnames = [
                "chave_acesso", "numero_nfse", "serie", "tipo", "status",
                "motivo_cancelamento", "data_cancelamento", "nsu_cancelamento",
                "data_emissao", "data_competencia", "nsu", "cnpj_consultado",
                "prestador_cnpj_cpf", "prestador_nome", "prestador_im", "prestador_municipio",
                "tomador_cnpj_cpf", "tomador_nome", "tomador_im", "tomador_municipio",
                "valor_servico", "valor_liquido", "valor_iss", "iss_retido", "aliquota_iss",
                "valor_pis", "valor_cofins", "valor_inss", "valor_ir", "valor_csll",
                "codigo_tributacao_nacional", "discriminacao_servico", "caminho_xml", "caminho_pdf"
            ]

            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                for n in notas:
                    writer.writerow(n)

            messagebox.showinfo("Exportação Concluída", f"Relatório exportado com sucesso com {len(notas)} nota(s)!\nArquivo salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", f"Falha ao exportar arquivo CSV: {e}")

    def sync_local_files_to_db(self):
        if not HAS_DATABASE:
            return

        self.btn_sync_db.configure(state="disabled", text="⏳ Sincronizando...")
        self.log("\n[Banco de Dados] Iniciando varredura e sincronização de arquivos locais...")

        def worker():
            try:
                stats = database.import_existing_data(verbose=False)
                self.after(0, lambda: self._on_sync_db_done(stats))
            except Exception as e:
                self.after(0, lambda: self._on_sync_db_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_sync_db_done(self, stats):
        self.btn_sync_db.configure(state="normal", text="🔄 Importar / Sincronizar Arquivos Locais")
        msg = (
            f"Sincronização concluída!\n"
            f"  - XMLs processados/atualizados: {stats.get('xmls_importados', 0)}\n"
            f"  - Notas canceladas reconhecidas: {stats.get('canceladas_atualizadas', 0)}\n"
            f"  - Entradas NSU indexadas: {stats.get('nsu_index_importados', 0)}\n"
            f"  - Erros encontrados: {stats.get('erros', 0)}"
        )
        self.log(f"\n[Banco de Dados] {msg}")
        self.refresh_database_view()
        messagebox.showinfo("Sincronização do Banco de Dados", msg)

    def _on_sync_db_error(self, err_msg):
        self.btn_sync_db.configure(state="normal", text="🔄 Importar / Sincronizar Arquivos Locais")
        self.log(f"\n[Banco de Dados] [ERRO] {err_msg}")
        messagebox.showerror("Erro na Sincronização", f"Erro ao sincronizar arquivos locais com o banco:\n{err_msg}")

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
