#!/usr/bin/env python3
import os
import sys
import getpass
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization

def main():
    print("=== Conversor de Certificado Digital: PFX/P12 para PEM ===")
    print("Este script extrai a chave privada desprotegida e o certificado para uso com mTLS (requests).\n")
    
    # Verifica argumentos CLI, senão pergunta de forma interativa
    if len(sys.argv) >= 2:
        pfx_path = sys.argv[1]
    else:
        pfx_path = input("Caminho para o arquivo .pfx ou .p12: ").strip()
        
    # Remove aspas caso o usuário tenha arrastado o arquivo para o terminal
    pfx_path = pfx_path.strip("'\"")
        
    if not os.path.exists(pfx_path):
        print(f"Erro: O arquivo ou diretório '{pfx_path}' não foi encontrado.")
        return 1
        
    if os.path.isdir(pfx_path):
        print(f"\nO caminho informado é um diretório. Procurando certificados (.pfx ou .p12) em '{pfx_path}'...")
        arquivos = [f for f in os.listdir(pfx_path) if f.lower().endswith(('.pfx', '.p12'))]
        if not arquivos:
            print("Nenhum arquivo .pfx ou .p12 foi encontrado neste diretório.")
            return 1
        print("Certificados encontrados:")
        for idx, arq in enumerate(arquivos, 1):
            print(f"  {idx} - {arq}")
        try:
            opcao = input(f"Selecione o número do certificado (1-{len(arquivos)}): ").strip()
            if not opcao.isdigit() or not (1 <= int(opcao) <= len(arquivos)):
                print("Opção inválida.")
                return 1
            pfx_path = os.path.join(pfx_path, arquivos[int(opcao) - 1])
            print(f"Arquivo selecionado: {pfx_path}")
        except (KeyboardInterrupt, SystemExit):
            print("\nOperação cancelada.")
            return 1
        
    if len(sys.argv) >= 3:
        password = sys.argv[2]
    else:
        password = getpass.getpass("Senha do certificado (pressione Enter se não houver): ")

    if len(sys.argv) >= 4:
        pem_path = sys.argv[3]
    else:
        default_pem = os.path.splitext(pfx_path)[0] + ".pem"
        pem_path = input(f"Caminho do arquivo PEM de saída [Padrão: {default_pem}]: ").strip()
        if not pem_path:
            pem_path = default_pem
            
    pem_path = pem_path.strip("'\"")

    print("\nLendo arquivo PFX...")
    try:
        with open(pfx_path, "rb") as f:
            pfx_data = f.read()

        # Carrega o arquivo PKCS12 (PFX)
        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
            pfx_data,
            password.encode('utf-8') if password else None
        )

        print("Gravando chaves e certificados no arquivo PEM...")
        with open(pem_path, "wb") as f_out:
            # Escreve a chave privada desprotegida (como exigido pela biblioteca requests do Python)
            if private_key:
                pem_key = private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                )
                f_out.write(pem_key)
                print("- Chave privada adicionada.")
            else:
                print("Aviso: Chave privada não encontrada no arquivo PFX.")

            # Escreve o certificado principal
            if certificate:
                pem_cert = certificate.public_bytes(
                    encoding=serialization.Encoding.PEM
                )
                f_out.write(pem_cert)
                print("- Certificado principal adicionado.")
            else:
                print("Aviso: Certificado principal não encontrado no arquivo PFX.")

            # Escreve a cadeia de certificados intermediários (CA chain)
            if additional_certificates:
                print(f"- Encontrados {len(additional_certificates)} certificados intermediários.")
                for cert in additional_certificates:
                    f_out.write(cert.public_bytes(serialization.Encoding.PEM))
                print("- Certificados intermediários adicionados.")

        print(f"\nSucesso! Arquivo convertido salvo em: {pem_path}")
        print("Agora você pode usar este arquivo PEM para autenticar as requisições na API.")
        return 0

    except Exception as e:
        print(f"\nErro durante a conversão: {e}")
        print("Dica: Verifique se a senha informada está correta.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
