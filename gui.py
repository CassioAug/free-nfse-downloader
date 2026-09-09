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

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import subprocess
import shutil
import webbrowser
from version import __version__

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"Free NFS-e Downloader v{__version__}")
        self.geometry("900x700")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

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

        self.log_box = ctk.CTkTextbox(self, height=200)
        self.log_box.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.log_box.configure(state="disabled")

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
                process = subprocess.Popen(
                    cmd,
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

    def setup_download_tab(self):
        frame = ctk.CTkFrame(self.tab_download)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Certificate Type
        self.cert_type_var = tk.StringVar(value="1")

        ctk.CTkLabel(frame, text="Tipo de Certificado:").grid(row=0, column=0, padx=10, pady=10, sticky="w")

        radio_frame = ctk.CTkFrame(frame, fg_color="transparent")
        radio_frame.grid(row=0, column=1, columnspan=2, sticky="w")
        self.rb_pem = ctk.CTkRadioButton(radio_frame, text="Arquivo PEM (A1)", variable=self.cert_type_var, value="1", command=self.update_download_ui)
        self.rb_pem.pack(side="left", padx=(0, 20))
        self.rb_a3 = ctk.CTkRadioButton(radio_frame, text="Token USB (A3)", variable=self.cert_type_var, value="2", command=self.update_download_ui)
        self.rb_a3.pack(side="left")

        # Certificate Selection (PEM only or A3 index)
        self.lbl_cert = ctk.CTkLabel(frame, text="Certificado PEM:")
        self.lbl_cert.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.cert_entry = ctk.CTkEntry(frame, placeholder_text="Será buscado em ./certificados")
        self.cert_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # A3 Index
        self.lbl_a3_index = ctk.CTkLabel(frame, text="Índice do Token A3:")
        self.a3_index_entry = ctk.CTkEntry(frame, placeholder_text="1")

        # CNPJ
        ctk.CTkLabel(frame, text="CNPJ (14 dígitos):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.cnpj_entry = ctk.CTkEntry(frame, placeholder_text="Deixe vazio para automático")
        self.cnpj_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Start Date
        ctk.CTkLabel(frame, text="Data Inicial (DD/MM/YYYY):").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.start_date_entry = ctk.CTkEntry(frame, placeholder_text="Ex: 01/01/2026", width=180)
        self.start_date_entry.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        # End Date
        ctk.CTkLabel(frame, text="Data Final (DD/MM/YYYY):").grid(row=4, column=0, padx=10, pady=10, sticky="w")
        self.end_date_entry = ctk.CTkEntry(frame, placeholder_text="Ex: 31/01/2026 (Deixe vazio para hoje)", width=280)
        self.end_date_entry.grid(row=4, column=1, padx=10, pady=10, sticky="w")

        # Start Button
        self.btn_start_download = ctk.CTkButton(frame, text="Iniciar Download", command=self.start_download)
        self.btn_start_download.grid(row=5, column=0, columnspan=3, pady=20)

        # We also need dummy buttons for other tabs so they can be disabled initially
        self.btn_convert_pfx = ctk.CTkButton(self.tab_convert_pfx, text="")
        self.btn_organize = ctk.CTkButton(self.tab_organize, text="")
        self.btn_convert_xml = ctk.CTkButton(self.tab_xml_pdf, text="")

        self.update_download_ui()

    def update_download_ui(self):
        if self.cert_type_var.get() == "1":
            self.lbl_cert.grid(row=1, column=0, padx=10, pady=10, sticky="w")
            self.cert_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

            self.lbl_a3_index.grid_remove()
            self.a3_index_entry.grid_remove()
        else:
            self.lbl_cert.grid_remove()
            self.cert_entry.grid_remove()

            self.lbl_a3_index.grid(row=1, column=0, padx=10, pady=10, sticky="w")
            self.a3_index_entry.grid(row=1, column=1, padx=10, pady=10, sticky="w")

    def start_download(self):
        cert_type = self.cert_type_var.get()
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip()
        cnpj = self.cnpj_entry.get().strip()

        if not start_date:
            messagebox.showerror("Erro", "A Data Inicial é obrigatória.")
            return

        inputs = [cert_type]

        if cert_type == "1": # PEM
            # We assume there's a file in ./certificados
            pem_name = self.cert_entry.get().strip()
            cert_dir = "./certificados"

            if os.path.exists(cert_dir):
                files = [f for f in os.listdir(cert_dir) if f.lower().endswith('.pem')]
                if len(files) > 1:
                    if not pem_name:
                        messagebox.showwarning("Aviso", f"Existem múltiplos arquivos PEM em {cert_dir}. O primeiro será selecionado automaticamente (ou informe um índice no campo 'Certificado PEM').")
                        inputs.append("1") # Seleciona o primeiro
                    elif pem_name.isdigit():
                        inputs.append(pem_name)
                    else:
                        try:
                            idx = files.index(pem_name) + 1
                            inputs.append(str(idx))
                        except ValueError:
                            inputs.append("1")
                elif len(files) == 1:
                    # Nenhuma entrada é solicitada pelo script se houver apenas 1
                    pass
                else:
                    messagebox.showerror("Erro", "Nenhum arquivo .pem encontrado em ./certificados")
                    return
            else:
                 messagebox.showerror("Erro", "Pasta ./certificados não encontrada")
                 return
        else: # A3
            # Se houver apenas 1 certificado de token, o script seleciona automaticamente
            # e não solicita índice via stdin (evita descompasso que afetava a Data Inicial).
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

        # Se houver CNPJ, o script pode pedir se o auto extrair falhar, mas vamos assumir que não precisa
        # Data
        inputs.append(start_date)
        if end_date:
            inputs.append(end_date)
        else:
            inputs.append("") # Deixa vazio para pegar a data de hoje

        self.log_box.delete("0.0", "end")
        self.run_command_interactive(
            [sys.executable, "download_nfse.py"],
            inputs,
            "Download Finalizado.",
            "Erro no Download."
        )


    def setup_convert_pfx_tab(self):
        frame = ctk.CTkFrame(self.tab_convert_pfx)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # PFX Path
        ctk.CTkLabel(frame, text="Arquivo PFX/P12:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.pfx_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./certificados/meu_cert.pfx")
        self.pfx_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_pfx = ctk.CTkButton(frame, text="Procurar...", command=self.browse_pfx)
        self.btn_browse_pfx.grid(row=0, column=2, padx=10, pady=10)

        # Password
        ctk.CTkLabel(frame, text="Senha do Certificado:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.pfx_pass_entry = ctk.CTkEntry(frame, show="*")
        self.pfx_pass_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # PEM Output Path (Optional)
        ctk.CTkLabel(frame, text="Arquivo PEM (Saída):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.pem_out_entry = ctk.CTkEntry(frame, placeholder_text="Opcional. Padrão: mesmo nome na pasta ./certificados")
        self.pem_out_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Start Button
        self.btn_convert_pfx = ctk.CTkButton(frame, text="Converter PFX -> PEM", command=self.start_convert_pfx)
        self.btn_convert_pfx.grid(row=3, column=0, columnspan=3, pady=20)

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

        cmd = [sys.executable, "convert_pfx.py", pfx_path, pfx_pass]
        if pem_out:
            cmd.append(pem_out)

        self.log_box.delete("0.0", "end")
        self.run_command(cmd, "Conversão Finalizada.", "Erro na Conversão.")



    def setup_organize_tab(self):
        frame = ctk.CTkFrame(self.tab_organize)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # XML Directory
        ctk.CTkLabel(frame, text="Pasta dos XMLs:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.org_dir_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./notas_fiscais/12345678000199")
        self.org_dir_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_org = ctk.CTkButton(frame, text="Procurar...", command=self.browse_org)
        self.btn_browse_org.grid(row=0, column=2, padx=10, pady=10)

        # CNPJ
        ctk.CTkLabel(frame, text="CNPJ (14 dígitos):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.org_cnpj_entry = ctk.CTkEntry(frame, placeholder_text="Apenas números")
        self.org_cnpj_entry.grid(row=1, column=1, columnspan=2, padx=10, pady=10, sticky="ew")

        # Start Button
        self.btn_organize = ctk.CTkButton(frame, text="Organizar Notas", command=self.start_organize)
        self.btn_organize.grid(row=2, column=0, columnspan=3, pady=20)

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

        cmd = [sys.executable, "organize_nfse.py", "--dir", directory, "--cnpj", cnpj]

        self.log_box.delete("0.0", "end")
        self.run_command(cmd, "Organização Finalizada.", "Erro na Organização.")



    def setup_xml_pdf_tab(self):
        frame = ctk.CTkFrame(self.tab_xml_pdf)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        frame.grid_columnconfigure(1, weight=1)

        # Input Path (File or Directory)
        ctk.CTkLabel(frame, text="XML ou Pasta:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.xml_input_entry = ctk.CTkEntry(frame, placeholder_text="Ex: ./notas_fiscais")
        self.xml_input_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_xml = ctk.CTkButton(frame, text="Procurar...", command=self.browse_xml)
        self.btn_browse_xml.grid(row=0, column=2, padx=10, pady=10)

        # Output Path (Optional)
        ctk.CTkLabel(frame, text="Pasta Destino (Opcional):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.pdf_out_entry = ctk.CTkEntry(frame, placeholder_text="Deixe vazio para mesma pasta do XML")
        self.pdf_out_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.btn_browse_pdf_out = ctk.CTkButton(frame, text="Procurar...", command=self.browse_pdf_out)
        self.btn_browse_pdf_out.grid(row=1, column=2, padx=10, pady=10)

        # Force overwrite
        self.force_var = tk.BooleanVar(value=False)
        self.chk_force = ctk.CTkCheckBox(frame, text="Forçar conversão (Sobrescrever PDFs existentes)", variable=self.force_var)
        self.chk_force.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="w")

        # Start Button
        self.btn_convert_xml = ctk.CTkButton(frame, text="Converter XML -> PDF", command=self.start_convert_xml)
        self.btn_convert_xml.grid(row=3, column=0, columnspan=3, pady=20)

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

        cmd = [sys.executable, "xml_to_pdf.py"]

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
        lbl_version.pack(pady=(0, 20))

        lbl_desc = ctk.CTkLabel(
            container,
            text="Automação, sincronização e download em lote de Notas Fiscais de Serviços\nEletrônicas (NFS-e) diretamente da API do Ambiente de Dados Nacional.",
            justify="center",
            font=ctk.CTkFont(size=13)
        )
        lbl_desc.pack(pady=(0, 25))

        lbl_author = ctk.CTkLabel(
            container,
            text="Desenvolvido por: Cássio Augusto Couto Soares (CassioAug)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_author.pack(pady=(0, 15))

        btn_github = ctk.CTkButton(
            container,
            text="🌐 Abrir Repositório no GitHub",
            command=lambda: webbrowser.open("https://github.com/CassioAug/free-nfse-downloader"),
            width=260,
            height=36
        )
        btn_github.pack(pady=(0, 25))

        lbl_license = ctk.CTkLabel(
            container,
            text="Licença: GNU General Public License v3.0 (GPLv3)",
            font=ctk.CTkFont(size=12, slant="italic")
        )
        lbl_license.pack(pady=(0, 5))


if __name__ == "__main__":
    app = App()
    app.mainloop()
