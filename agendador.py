import sys
import os
import json
import time
import threading
import schedule
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.firefox import GeckoDriverManager

import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar

from PIL import Image, ImageTk 


import subprocess
import os
import sys
import socket

# Aguarda conexão com a internet (tenta X vezes com Y segundos entre elas)
#essa def coloquei posteriormente por causa do .exe, que ao inicializar junto com o pc precisa de conexão Wi-fi pra funcionar
#(A gente pode configurar no prório agendador de tarefas para aguardar um tempo apos ligarmos a maquina)
#Muito provavelemente não será necessário
def aguardar_conexao(retries=10, delay=5):
    for tentativa in range(retries):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            print("✅ Conexão com a internet detectada.")
            return True
        except OSError:
            print(f"⏳ Sem internet ainda. Tentativa {tentativa + 1}/{retries}. Aguardando {delay}s...")
            time.sleep(delay)
    print("❌ Internet não disponível após várias tentativas.")
    return False

# Função pronta para registrar o script no Agendador do Windows pra rodar no login, não pude validar pois não
#possuo acesso ADM, sendo necessário a execução como Administrador

def registrar_no_agendador():
    # Detecta automaticamente se está rodando como .exe ou .py
    if getattr(sys, 'frozen', False):
        caminho_script = os.path.abspath(sys.executable)
    else:
        caminho_script = os.path.abspath(__file__)

    print(f"📝 Registrando no agendador: {caminho_script}")

    comando = [
        'schtasks',
        '/Create',
        '/SC', 'ONLOGON',
        '/TN', 'wisebot',
        '/TR', f'"{caminho_script}"',
        '/RL', 'HIGHEST',
        '/F'  # Força sobrescrever se já existir
    ]

    try:
        resultado = subprocess.run(comando, capture_output=True, text=True)
        if resultado.returncode == 0:
            print("✅ WiseBot registrado no Agendador de Tarefas com sucesso!")
        else:
            print(f"❌ Erro ao registrar: {resultado.stderr}")
    except Exception as e:
        print(f"❌ Exceção ao tentar registrar no agendador: {e}")



# Diretório base do script/executável
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Caminhos corrigidos para leitura/gravação de arquivos
PREFERENCIAS_ARQUIVO = os.path.join(base_dir, "preferencias.json")
COOKIES_ARQUIVO = os.path.join(base_dir, "cookies.json")
CONFIG_ARQUIVO = os.path.join(base_dir, "config.json")
DIAS_RESERVADOS_ARQUIVO = os.path.join(base_dir, "dias_reservados.json")
LOGO_PATH = os.path.join(base_dir, "logo.png")  # caso use com ImageTk

# Abre janela pra pedir email/senha e salva no config.json, essa parte do login funciona como a automação das Salas
def pedir_credenciais_custom():
    root = tk.Tk()
    root.withdraw()

    icon_img = tk.PhotoImage(file=LOGO_PATH)

    login_win = tk.Toplevel()
    login_win.title("Login WiseBot")
    login_win.iconphoto(False, icon_img)

    login_win.geometry("350x220")
    login_win.configure(bg="#F4F4F9")
    login_win.resizable(False, False)

    entry_style = {"font": ("Segoe UI", 11), "relief": tk.FLAT, "bg": "#FFFFFF", "fg": "#1D3557", "bd": 1}

    tk.Label(login_win, text="Email:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
    email_entry = tk.Entry(login_win, width=30, **entry_style)
    email_entry.pack(pady=5, padx=20)

    tk.Label(login_win, text="Senha:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12, "bold")).pack(pady=5)
    senha_entry = tk.Entry(login_win, width=30, show="*", **entry_style)
    senha_entry.pack(pady=5, padx=20)

    def salvar_e_sair():
        email = email_entry.get()
        senha = senha_entry.get()
        if not email or not senha:
            messagebox.showerror("Erro", "Preencha ambos os campos.", parent=login_win)
            return
        with open(CONFIG_ARQUIVO, "w", encoding="utf-8") as f:
            json.dump({"email": email, "senha": senha}, f, indent=4, ensure_ascii=False)
        messagebox.showinfo("Sucesso", "Credenciais salvas!", parent=login_win)
        login_win.destroy()
        root.destroy()

    btn_entrar = tk.Button(
        login_win,
        text="Entrar",
        command=salvar_e_sair,
        bg="#0077B6",
        fg="#FFFFFF",
        activebackground="#005792",
        activeforeground="#FFFFFF",
        font=("Segoe UI", 11, "bold"),
        relief=tk.FLAT,
        bd=0,
        padx=20,
        pady=10,
        width=20
    )
    btn_entrar.pack(pady=(15, 20))

    login_win.mainloop()

    with open(CONFIG_ARQUIVO, "r", encoding="utf-8") as f:
        config = json.load(f)
        return config.get("email"), config.get("senha")

# Carrega email e senha do config.json (ou chama a janela se não tiver)
def carregar_credenciais():
    if CONFIG_ARQUIVO.exists():
        with open(CONFIG_ARQUIVO, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("email"), config.get("senha")
    else:
        return pedir_credenciais_custom()

email, senha = carregar_credenciais()

if not email or not senha:
    raise ValueError("Email ou senha não encontrados no arquivo de configuração.")


 # Verifica se o navegador existe no caminho ou na lista de caminhos.
def navegador_disponivel(caminho_ou_lista):
   
    if isinstance(caminho_ou_lista, list):
        for caminho in caminho_ou_lista:
            if os.path.exists(caminho):
                return True
        return False
    else:
        return os.path.exists(caminho_ou_lista)


def inicializar_navegador(headless=False):
    chrome_caminhos = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]

    edge_caminho = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    firefox_caminhos = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
    ]

    if navegador_disponivel(edge_caminho):
        print("✅ Chrome encontrado! Iniciando com ChromeDriver...")
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless")
        navegador = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        return navegador

    elif navegador_disponivel(chrome_caminhos):
        print("✅ Edge encontrado! Iniciando com EdgeDriver...")
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless")
        navegador = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=options)
        return navegador

    elif navegador_disponivel(firefox_caminhos):
        print("✅ Firefox encontrado! Iniciando com GeckoDriver...")
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        navegador = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
        return navegador

    else:
        print("❌ Nenhum navegador compatível encontrado.")
        sys.exit("Por favor, instale o Google Chrome, Microsoft Edge ou Mozilla Firefox para continuar.")


# Faz login no Wise, pega os cookies e salva no cookies.json
def fazer_login(headless=False):
    global navegador
    navegador = inicializar_navegador(headless=headless)
    try:
        navegador.get("https://id.wiseoffices.com.br/realms/wiseoffices/protocol/openid-connect/auth?client_id=wiseoffices&redirect_uri=https%3A%2F%2Fapp.wiseoffices.com.br%2Fdeimos%2Fcallback&response_type=code&scope=openid+profile+email")
        navegador.maximize_window()

        campo_email = WebDriverWait(navegador, 10).until(EC.presence_of_element_located((By.ID, "username")))
        campo_email.send_keys(email)

        campo_continuar = WebDriverWait(navegador, 10).until(EC.element_to_be_clickable((By.ID, "kc-login")))
        campo_continuar.click()

        input_senha = WebDriverWait(navegador, 10).until(EC.presence_of_element_located((By.ID, "password")))
        input_senha.send_keys(senha)

        campo_continuar_dois = WebDriverWait(navegador, 10).until(EC.element_to_be_clickable((By.NAME, "login")))
        campo_continuar_dois.click()

        WebDriverWait(navegador, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "styles__ComplementsSelectBox-sc-1qitxh9-1"))
        )
        print('✅ Logado com sucesso')

        cookies = navegador.get_cookies()
        with open("cookies.json", "w") as f:
            json.dump(cookies, f)
        print("✅ Cookies salvos em cookies.json")

    except Exception as e:
        print(f"❌ Erro ao fazer login: {e}")
        navegador.quit()
        sys.exit(1)
    finally:
        return

#dicionario com todas cadeiras e os respectivos ids do 2 andar do prédio
CADEIRAS_IDS = {
    "Cabine 2": "7638", "Sala de entrevista": "7623", "Sala 2": "7632", "Sala 1": "7630", "Cabine 1": "7637",
    "H2-001": "7602", "H2-002": "7603", "H2-003": "7604", "H2-004": "7605", "H2-005": "7606", "H2-006": "7607", 
    "H2-007": "7608", "H2-008": "7609",
    "OS001": "7613", "OS002": "7496", "OS003": "7497", "OS004": "7498", "OS005": "7503", "OS006": "7504",
    "OS007": "7505", "OS008": "7506", "OS009": "7507", "OS010": "7508", "OS011": "7618", "OS012": "6780",
    "OS013": "6787", "OS014": "6788", "OS015": "6789", "OS016": "6790", "OS017": "6791", "OS018": "6792",
    "OS019": "6793", "OS020": "7617", "OS2-021": "7614", "OS2-022": "7694", "OS2-023": "6795", "OS2-024": "6796",
    "OS2-025": "6797", "OS2-026": "6798", "OS2-027": "6799", "OS2-028": "6800", "OS2-029": "6801", "OS2-030": "6802",
    "OS2-031": "6803", "OS2-032": "7572", "OS2-033": "6804", "OS2-034": "6805", "OS2-035": "6086", "OS2-036": "7573",
    "OS2-037": "6807", "OS2-038": "6808", "OS2-039": "6809", "OS2-040": "6810", "OS2-041": "6811", "OS2-042": "6812",
    "OS2-043": "6813", "OS2-044": "6814", "OS2-045": "6815", "OS2-046": "7574", "OS2-047": "6816", "OS2-048": "6817",
    "OS2-049": "6818", "OS2-050": "6819", "OS2-051": "6820", "OS2-052": "6821", "OS2-053": "6822", "OS2-054": "6823",
    "OS2-055": "7575", "OS2-056": "6824", "OS2-057": "6825", "OS2-058": "6826", "OS2-059": "6827", "OS2-060": "6828",
    "OS2-061": "6829", "OS2-062": "6830", "OS2-063": "6831", "OS2-064": "6832", "OS2-065": "7576", "OS2-066": "6833",
    "OS2-067": "6834", "OS2-068": "6835", "OS2-069": "6836", "OS2-070": "6837", "OS2-071": "6838", "OS2-072": "6839",
    "OS2-073": "6840", "OS2-074": "6841", "OS2-075": "6842", "OS2-076": "6843", "OS2-077": "6844", "OS2-078": "6845",
    "OS2-079": "6846", "OS2-080": "6847", "OS2-081": "6848", "OS2-082": "6849", "OS2-083": "6850", "OS2-084": "6851",
    "OS2-085": "7577", "OS2-086": "6852", "OS2-087": "7615", "OS2-088": "6854", "OS2-089": "7578", "OS2-090": "6855",
    "OS2-091": "6856", "OS2-092": "7616", "OS2-093": "6857", "OS2-094": "6858",
    "OS2095": "7470", "OS2096": "7483", "OS2097": "7484", "OS2098": "7486", "OS2099": "7487", "OS2100": "7488",
    "OS2101": "7489", "OS2102": "7490", "OS2103": "7491", "OS2104": "7492", "OS2105": "7493", "OS2106": "6878",
    "OS2107": "6879", "OS2108": "6880", "OS2109": "7590", "OS2110": "7591", "OS2111": "7592", "OS2112": "7593",
    "OS2113": "6986", "OS2114": "6987", "OS2115": "7027", "OS2116": "7028", "OS2117": "7029", "OS2118": "7030",
    "OS2119": "7031", "OS2120": "7032", "OS2121": "7033", "OS2122": "7034", "OS2123": "7035", "OS2124": "7036",
    "OS2125": "7037", "OS2126": "7038", "OS2127": "70339", "OS2128": "7040", "OS2129": "7041", "OS2130": "7042",
    "OS2131": "7043", "OS2132": "7044", "OS2133": "7045", "OS2134": "7046", "OS2135": "7047", "OS2136": "7048",
    "OS2137": "7049", "OS2138": "7050", "OS2139": "7051", "OS2140": "7052", "OS2141": "7053", "OS2142": "7054",
    "OS2143": "7055", "OS2144": "7061", "OS2145": "7062", "OS2146": "7063", "OS2147": "7064", "OS2148": "7065",
    "OS2149": "7073", "OS2150": "7074", "OS2151": "7077", "OS2152": "7078", "OS2153": "7079", "OS2154": "7080",
    "OS2155": "7081", "OS2156": "7082", "OS2157": "7083", "OS2158": "7084", "OS2159": "7085", "OS2160": "7104",
    "OS2161": "7105", "OS2162": "7106", "OS2163": "7107", "OS2164": "7108", "OS2165": "7109", "OS2166": "7110",
    "OS2167": "7111", "OS2168": "7112", "OS2169": "7113", "OS2170": "7114", "OS2171": "7115", "OS2172": "7116",
    "OS2173": "7117", "OS2174": "7118", "OS2175": "7119", "OS2176": "7120", "OS2177": "721", "OS2178": "7122",
    "OS2179": "7123", "OS2180": "71124", "OS2181": "7125", "OS2182": "7126", "OS2183": "7127", "OS2184": "7128",
    "OS2185": "7129", "OS2186": "7139", "OS2187": "7140", "OS2188": "7141"
}

# Carrega cookies salvos do último login
def carregar_cookies():
    if os.path.exists(COOKIES_ARQUIVO):
        with open(COOKIES_ARQUIVO, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# Usa os cookies pra pegar o ID do usuário logado
def obter_id_usuario(cookies):
    url = "https://app.wiseoffices.com.br/api/v1/me"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        
        # Retorna diretamente o ID do usuário
        return response.json().get("id")
        
    except requests.RequestException as e:
        print(f"❌ Erro ao obter ID do usuário: {e}")
        return None
    
 # Testa se os cookies ainda estão válidos na API do Wise (Essa é uma questão importante, como não enviamos todas 
 # requisições de uma só vez, os cookies podem ficar inválidos depois de um tempo, e nosso intuito é sempre termos
 # estes cookies para podermos usar o schedule corretamente)   
def verificar_cookies_validos(cookies):
    url = "https://app.wiseoffices.com.br/api/v1/me"
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=5)
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"❌ Erro ao verificar cookies: {e}")
        return False

# Verifica se já existe uma reserva feita pra uma data e cadeira
def verificar_reserva_existente(cookies, data_verificar,):
    url = "https://app.wiseoffices.com.br/api/v1/u/reservas/dias-reservados"
    headers = {
        "accept": "*/*",
        "user-agent": "Mozilla/5.0"
    }
    params = {
        "data": data_verificar,
        "paraTerceiros": "false"
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10)
        response.raise_for_status()
        reservas = response.json()
        
        print(f"🔍 Resposta bruta de dias reservados: {reservas}")

        if isinstance(reservas, list):
            if data_verificar in reservas:
                print(f"✅ Reserva já existe para {data_verificar} e foi feita por VOCÊ.")
                return True
            else:
                return False
        else:
            print("⚠️ Resposta inesperada ao verificar reservas.")
            return False

    except requests.RequestException as e:
        print(f"❌ Erro ao verificar reservas existentes: {e}")
        return False




PREFERENCIAS_ARQUIVO = "preferencias.json"

# Salva preferências de reserva (cadeira, dias, horários etc) em JSON
def salvar_preferencias(cadeira, data_inicio, dias_semana, intervalo, horario_inicio, horario_fim):
    preferencias = {
        "cadeira": cadeira,
        "data_inicio": data_inicio,
        "dias_semana": dias_semana,
        "intervalo": intervalo,
        "horario_inicio": horario_inicio,
        "horario_fim": horario_fim
    }
    
    with open(PREFERENCIAS_ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(preferencias, f, indent=4, ensure_ascii=False)
    
    messagebox.showinfo("Sucesso", "Preferências agendadas para reserva!")


# Lê preferências salvas em preferencias.json
def carregar_preferencias():
    with open(PREFERENCIAS_ARQUIVO, "r", encoding="utf-8") as f:
        return json.load(f)
    
# Lê lista de dias já reservados do JSON
def carregar_dias_reservados():
    caminho = "dias_reservados.json"
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Salva uma data como já reservada no JSON
def salvar_dia_reservado(data_str):
    caminho = "dias_reservados.json"
    dias = carregar_dias_reservados()
    if data_str not in dias:
        dias.append(data_str)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dias, f, indent=4, ensure_ascii=False)

# Faz as tentativas reais de reserva, com base nas preferências e nas regras da API
def enviar_reserva(cookies):
    preferencias = carregar_preferencias()
    if not preferencias:
        print("❌ Não foi possível carregar as preferências.")
        return False

    cadeira_nome = preferencias["cadeira"]
    cadeira_id = CADEIRAS_IDS.get(cadeira_nome)

    if not cadeira_id:
        print(f"❌ Erro: Cadeira '{cadeira_nome}' não encontrada no dicionário CADEIRAS_IDS.")
        return False

    horario_inicio = preferencias["horario_inicio"]
    horario_fim = preferencias["horario_fim"]
    dias_semana_permitidos = preferencias["dias_semana"]

    dias_semana_traduzidos = {
        "Monday": "Segunda",
        "Tuesday": "Terça",
        "Wednesday": "Quarta",
        "Thursday": "Quinta",
        "Friday": "Sexta",
        "Saturday": "Sábado",
        "Sunday": "Domingo"
    }

    dias_reservados = carregar_dias_reservados()

    meu_id = obter_id_usuario(cookies)
    if not meu_id:
        print("❌ Não foi possível obter o ID do usuário.")
        return False

    hoje = datetime.now()
    for offset in range(7):
        data_reserva = hoje + timedelta(days=offset)
        data_reserva_str = data_reserva.strftime("%Y-%m-%d")

        if data_reserva_str in dias_reservados:
            print(f"⚠️ Já foi feita tentativa de reserva com sucesso para {data_reserva_str}. Pulando.")
            continue

        nome_dia_reserva = data_reserva.strftime("%A")
        dia_reserva_pt = dias_semana_traduzidos.get(nome_dia_reserva, nome_dia_reserva)

        if dia_reserva_pt not in dias_semana_permitidos:
            continue

        # 🔴 NOVA VERIFICAÇÃO: já existe reserva feita por VOCÊ?
        if verificar_reserva_existente(cookies, data_reserva_str, cadeira_id):
            salvar_dia_reservado(data_reserva_str)  # marca como reservado
            continue

        url = f"https://app.wiseoffices.com.br/api/v1/u/reservas/imoveis/3153/recursos/{cadeira_id}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://app.wiseoffices.com.br",
            "Referer": "https://app.wiseoffices.com.br/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        }

        payload = {
            "idsUsuariosConvidados": [meu_id],
            "visitantes": [],
            "dataInicio": f"{data_reserva_str} {horario_inicio}",
            "dataFim": f"{data_reserva_str} {horario_fim}",
            "descricao": None,
            "idUsuarioRepresentado": None,
            "tituloReuniao": None,
            "agora": False
        }

        try:
            print(f"📦 Enviando payload para {data_reserva_str}: {json.dumps(payload, indent=4)}")
            response = requests.post(url, json=payload, headers=headers, cookies=cookies, timeout=10)
            if response.status_code == 201:
                print(f"✅[STATUS] Reserva realizada para {data_reserva_str}!")
                salvar_dia_reservado(data_reserva_str)
            else:
                print(f"❌ Falha ao criar reserva para {data_reserva_str}: {response.status_code}")
                print(response.text)
        except requests.RequestException as e:
            print(f"❌ Erro de conexão para {data_reserva_str}: {e}")

    return True

# Verifica se reserva é possível e tenta novamente se os cookies tiverem expirado
def verificar_reserva(cookies=None):
    if cookies is None or not verificar_cookies_validos(cookies):
        print("🔄 Cookies expirados ou inválidos. Fazendo login novamente...")
        fazer_login(headless=True)
        cookies = carregar_cookies()

    if not cookies:
        print("❌ Cookies não encontrados após login. Não é possível continuar.")
        return

    print("🚀 Tentando criar reserva para amanhã...")
    sucesso = enviar_reserva(cookies)

    if sucesso:
        print("✅ Reserva criada com sucesso!")
    else:
        print("❌ Falha ao criar reserva.")

# Agendamento principal: itera dias e dispara reservas conforme preferência
def agendar_reserva():
    global cookies
    preferencias = carregar_preferencias()

    if not preferencias:
        print("❌ Não foi possível carregar as preferências.")
        return

    dias_semana_permitidos = preferencias["dias_semana"]

    # Verifica se os cookies ainda são válidos
    if not verificar_cookies_validos(cookies):
        print("🔄 Cookies expirados ou inválidos. Fazendo login novamente...")
        fazer_login(headless=True)
        cookies = carregar_cookies()

    # Verifica os próximos 7 dias
    hoje = datetime.now()
    for offset in range(7):
        data_reserva = hoje + timedelta(days=offset)
        nome_dia_reserva = data_reserva.strftime("%A")
        dia_reserva_pt = {
            "Monday": "Segunda",
            "Tuesday": "Terça",
            "Wednesday": "Quarta",
            "Thursday": "Quinta",
            "Friday": "Sexta",
            "Saturday": "Sábado",
            "Sunday": "Domingo"
        }.get(nome_dia_reserva, nome_dia_reserva)

        # Se for um dos dias permitidos, tenta criar a reserva
        if dia_reserva_pt in dias_semana_permitidos:
            print(f"🚀 Tentando criar reserva para {dia_reserva_pt} ({data_reserva.strftime('%Y-%m-%d')})...")
            verificar_reserva(cookies)

# Interface gráfica pro usuário configurar tudo (cadeira, dias, horário etc)
def criar_interface():
    root = tk.Tk()
    root.title("WiseBot - Configurar Reservas")
    root.geometry("400x600")
    root.configure(bg="#F4F4F9")
    root.resizable(False, False)

    # ✅ Correção: manter a referência da imagem
    icon_img = tk.PhotoImage(file=LOGO_PATH)
    root.iconphoto(False, icon_img)
    root.icon_img_ref = icon_img  # <- mantém a referência viva!

    # Centralização da janela
    window_width = 450
    window_height = 650
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width - window_width) / 2)
    y = int((screen_height - window_height) / 2) - 50
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Carregar a logo e redimensionar
    logo_img = Image.open(LOGO_PATH)
    logo_img = logo_img.resize((40, 40), Image.LANCZOS)
    logo_tk = ImageTk.PhotoImage(logo_img)

    # Mantém referência para evitar garbage collection
    root.logo_img_ref = logo_tk

    # Frame para o título com logo centralizado
    titulo_frame = tk.Frame(root, bg="#0077B6")
    titulo_frame.pack(fill=tk.X, pady=(10, 20))

    titulo_container = tk.Frame(titulo_frame, bg="#0077B6")
    titulo_container.pack(anchor=tk.CENTER)

    titulo_label = tk.Label(
        titulo_container,
        text="WiseBot",
        bg="#0077B6",
        fg="#FFFFFF",
        font=("Segoe UI", 18, "bold")
    )
    titulo_label.pack(side=tk.LEFT, padx=5)

    logo_label = tk.Label(titulo_container, image=logo_tk, bg="#0077B6")
    logo_label.image = logo_tk  # <- mantém referência
    logo_label.pack(side=tk.LEFT, padx=5)


    # Cadeiras
    tk.Label(root, text="Cadeira/Sala:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    cadeira_var = tk.StringVar(value=list(CADEIRAS_IDS.keys())[0])
    cadeira_menu = ttk.Combobox(root, textvariable=cadeira_var, values=list(CADEIRAS_IDS.keys()), state="readonly", width=35)
    cadeira_menu.pack(pady=5)

    # Data de Início
    tk.Label(root, text="Data de Início:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    data_inicio_var = tk.Entry(root, width=35, font=("Segoe UI", 10))
    data_inicio_var.insert(0, datetime.now().strftime("%Y-%m-%d"))
    data_inicio_var.pack(pady=5)

    def selecionar_data():
        calendario_win = tk.Toplevel(root)
        calendario_win.title("Selecionar Data de Início")
        calendario_win.geometry("350x400")
        calendario_win.configure(bg="#F4F4F9")

        cal = Calendar(calendario_win, selectmode="day", date_pattern="yyyy-mm-dd")
        cal.pack(pady=20)

        tk.Button(
            calendario_win, 
            text="Confirmar", 
            command=lambda: (data_inicio_var.delete(0, tk.END), data_inicio_var.insert(0, cal.get_date()), calendario_win.destroy()),
            bg="#0077B6",
            fg="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=5
        ).pack(pady=10)

    tk.Button(
        root, 
        text="Selecionar Data", 
        command=selecionar_data,
        bg="#0077B6",
        fg="#FFFFFF",
        font=("Segoe UI", 10, "bold"),
        relief=tk.FLAT,
        bd=0,
        padx=10,
        pady=5,
        width=30
    ).pack(pady=5)

    # Dias da Semana
    tk.Label(root, text="Dias da Semana:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    dias_semana_vars = {}
    dias_semana_frame = tk.Frame(root, bg="#F4F4F9")
    dias_semana_frame.pack()
    for dia in ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]:
        var = tk.BooleanVar()
        chk = tk.Checkbutton(dias_semana_frame, text=dia, variable=var, bg="#A8DADC", fg="#1D3557", font=("Segoe UI", 10, "bold"))
        chk.pack(side=tk.LEFT, padx=5, pady=5)
        dias_semana_vars[dia] = var

    # Intervalo de Repetição
    tk.Label(root, text="Repetir a cada X semanas:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    intervalo_var = tk.Entry(root, width=35, font=("Segoe UI", 10))
    intervalo_var.insert(0, "1")
    intervalo_var.pack(pady=5)

    # Horários de Início
    horarios_inicio = [f"{h:02d}:{m:02d}" for h in range(7, 18) for m in (0, 30) if h > 7 or m >= 30]
    tk.Label(root, text="Horário de Início:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    horario_inicio_var = ttk.Combobox(root, values=horarios_inicio, width=35, state="readonly")
    horario_inicio_var.set("07:30")
    horario_inicio_var.pack(pady=5)

    # Horários de Fim
    horarios_fim = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]
    tk.Label(root, text="Horário de Fim:", bg="#F4F4F9", fg="#1D3557", font=("Segoe UI", 12)).pack(pady=(15, 5))
    horario_fim_var = ttk.Combobox(root, values=horarios_fim, width=35, state="readonly")
    horario_fim_var.set("08:30")
    horario_fim_var.pack(pady=5)

    # Botão Confirmar
    tk.Button(
        root, 
        text="Confirmar", 
        command=lambda: salvar_preferencias(
            cadeira_var.get(), 
            data_inicio_var.get(), 
            [dia for dia, var in dias_semana_vars.items() if var.get()],
            int(intervalo_var.get()),
            horario_inicio_var.get(),
            horario_fim_var.get()
        ),
        bg="#0077B6",
        fg="#FFFFFF",
        font=("Segoe UI", 11, "bold"),
        relief=tk.FLAT,
        bd=0,
        padx=10,
        pady=10,
        width=30
    ).pack(pady=20)

    root.mainloop()


# Roda diariamente nos horários definidos e tenta reservar conforme preferência
def agendar_reserva():
    global cookies
    preferencias = carregar_preferencias()

    if not preferencias:
        print("❌ Não foi possível carregar as preferências.")
        return

    dias_semana_permitidos = preferencias["dias_semana"]

    if not verificar_cookies_validos(cookies):
        print("🔄 Cookies expirados ou inválidos. Fazendo login novamente...")
        fazer_login(headless=True)
        cookies = carregar_cookies()

    hoje = datetime.now()
    for offset in range(7):
        data_reserva = hoje + timedelta(days=offset)
        nome_dia_reserva = data_reserva.strftime("%A")
        dia_reserva_pt = {
            "Monday": "Segunda",
            "Tuesday": "Terça",
            "Wednesday": "Quarta",
            "Thursday": "Quinta",
            "Friday": "Sexta",
            "Saturday": "Sábado",
            "Sunday": "Domingo"
        }.get(nome_dia_reserva, nome_dia_reserva)

        if dia_reserva_pt in dias_semana_permitidos:
            print(f"🚀 Tentando criar reserva para {dia_reserva_pt} ({data_reserva.strftime('%Y-%m-%d')})...")
            verificar_reserva(cookies)


horarios_preferidos = [
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "15:50"
]

# Inicia a automação: se já tiver preferências, agenda tentativas diárias nos horários definidos via schedule.
# Se não tiver, abre interface pro usuário configurar e já registra a tarefa no Agendador do Windows.
# A função agendar_reserva roda diariamente e verifica se hoje ou amanhã é um dos dias escolhidos,
# e só então tenta fazer a reserva respeitando a limitação de antecedência da plataforma.
if __name__ == "__main__":
    if not aguardar_conexao():
        sys.exit("🚫 Não foi possível detectar conexão com a internet. Tente novamente mais tarde.")

    if os.path.exists(PREFERENCIAS_ARQUIVO):
        print("✅ Preferências encontradas. Pulando configuração e indo direto para o agendamento...")

        cookies = carregar_cookies()

        for horario in horarios_preferidos:
            print(f"⏰ Agendando reserva para: {horario}")
            schedule.every().day.at(horario).do(agendar_reserva)

        print("🔁 Iniciando loop do agendador...")
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Agendador interrompido manualmente. Encerrando...")

    else:
        print("⚠️ Preferências não encontradas. Executando configuração completa...")

        fazer_login()
        cookies = carregar_cookies()

        def iniciar_interface():
            criar_interface()
            registrar_no_agendador()

        interface_thread = threading.Thread(target=iniciar_interface)
        interface_thread.daemon = True
        interface_thread.start()

        for horario in horarios_preferidos:
            print(f"⏰ Agendando reserva para: {horario}")
            schedule.every().day.at(horario).do(agendar_reserva)

        print("🔁 Iniciando loop do agendador...")
        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Agendador interrompido manualmente. Encerrando...")





    


