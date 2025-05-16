# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import time
import re
import logging
import os # Import crucial para manipulação de caminhos

# --- Bloco de Configuração Inicial ---
# Logger de depuração inicial para caminhos (pode ser removido após a resolução do problema de deploy)
debug_logger = logging.getLogger("startup_debug")
stream_handler_debug = logging.StreamHandler()
formatter_debug = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
stream_handler_debug.setFormatter(formatter_debug)
if not debug_logger.handlers:
    debug_logger.addHandler(stream_handler_debug)
debug_logger.setLevel(logging.DEBUG)

debug_logger.info(f"INÍCIO DA EXECUÇÃO DO SCRIPT.")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SYSTEM_PROMPT_FILENAME = "system_prompt_aura.txt"
ABSOLUTE_PATH_TO_PROMPT_FILE = os.path.join(SCRIPT_DIR, SYSTEM_PROMPT_FILENAME)
debug_logger.info(f"Tentando localizar o arquivo de prompt em: {ABSOLUTE_PATH_TO_PROMPT_FILE}")
if os.path.exists(ABSOLUTE_PATH_TO_PROMPT_FILE):
    debug_logger.info(f"SUCESSO: Arquivo '{SYSTEM_PROMPT_FILENAME}' encontrado em '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
else:
    debug_logger.error(f"FALHA: Arquivo '{SYSTEM_PROMPT_FILENAME}' NÃO encontrado em '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
    debug_logger.error(f"Verifique se o arquivo está incluído no seu deployment e presente em: {SCRIPT_DIR}")
    try:
        debug_logger.info(f"Conteúdo do diretório '{SCRIPT_DIR}': {os.listdir(SCRIPT_DIR)}")
    except Exception as e_ls:
        debug_logger.error(f"Não foi possível listar o conteúdo de '{SCRIPT_DIR}': {e_ls}")


# Configuração do Logging Principal do Aplicativo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Constantes ---
SESSION_MESSAGES_KEY = "aura_messages"
SESSION_CHAT_KEY = "aura_chat_session"
SESSION_FEEDBACK_SUBMITTED_KEY = "aura_feedback_submitted"
DEFAULT_SYSTEM_INSTRUCTION = (
    "Você é Aura, um chatbot de apoio gentil e compreensivo. "
    "Seu objetivo é ouvir e oferecer conforto. "
    "Avise ao usuário que você é uma IA e não um terapeuta profissional. "
    "Se o arquivo de personalidade completo não pôde ser carregado, explique isso brevemente e peça desculpas pela experiência limitada."
)

# --- Bloco 1: Configuração da Página ---
st.set_page_config(
    page_title="Aura - Chatbot de Apoio",
    page_icon="💖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Bloco 2: Título e Descrição ---
st.title("💖 Aura Bem: Seu Companheiro Virtual")
st.caption("Um espaço seguro para conversar e encontrar acolhimento. Lembre-se, sou uma IA e não posso substituir um terapeuta profissional.")
st.divider()

# --- Bloco 3: Carregamento da System Instruction e Configuração da API ---
system_instruction_aura = ""
critical_error_loading_prompt = False

try:
    if os.path.exists(ABSOLUTE_PATH_TO_PROMPT_FILE):
        with open(ABSOLUTE_PATH_TO_PROMPT_FILE, "r", encoding="utf-8") as f:
            system_instruction_aura = f.read()
        logger.info(f"Instrução do sistema '{SYSTEM_PROMPT_FILENAME}' carregada com sucesso de '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
        if not system_instruction_aura.strip():
            logger.warning(f"O arquivo '{SYSTEM_PROMPT_FILENAME}' foi encontrado, mas está vazio. Usando fallback.")
            system_instruction_aura = DEFAULT_SYSTEM_INSTRUCTION
            st.warning(f"Atenção: O arquivo de personalidade da Aura ('{SYSTEM_PROMPT_FILENAME}') foi encontrado, mas está vazio. Usando configuração padrão.")
    else:
        logger.error(f"ERRO CRÍTICO: Arquivo de instrução do sistema '{SYSTEM_PROMPT_FILENAME}' não encontrado em '{ABSOLUTE_PATH_TO_PROMPT_FILE}'.")
        st.error(
            f"Erro Crítico de Configuração: O arquivo de personalidade da Aura ('{SYSTEM_PROMPT_FILENAME}') "
            f"não foi encontrado no local esperado: {ABSOLUTE_PATH_TO_PROMPT_FILE}. "
            "A Aura usará uma configuração muito básica e pode não funcionar como esperado. "
            "Por favor, verifique o deployment do aplicativo."
        )
        system_instruction_aura = DEFAULT_SYSTEM_INSTRUCTION
        critical_error_loading_prompt = True # Sinaliza um problema maior
except Exception as e:
    logger.error(f"Erro ao ler o arquivo de instrução do sistema '{ABSOLUTE_PATH_TO_PROMPT_FILE}': {e}", exc_info=True)
    st.error(f"Erro ao carregar a personalidade da Aura: {e}. A Aura usará uma configuração básica.")
    system_instruction_aura = DEFAULT_SYSTEM_INSTRUCTION
    critical_error_loading_prompt = True

# Configuração da API Key do Google
try:
    GOOGLE_API_KEY_APP = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY_APP)
    logger.info("Chave API do Google configurada com sucesso via Streamlit Secrets.")
except KeyError:
    logger.critical("Chave API do Google (GOOGLE_API_KEY) não encontrada nos Secrets do Streamlit. O APP NÃO FUNCIONARÁ.")
    st.error("ERRO GRAVE: A Chave API do Google não foi configurada nos 'Secrets' do Streamlit. O aplicativo não pode se conectar à IA. Por favor, configure-a.")
    st.stop() # Impede a continuação se a API key não estiver presente
except Exception as e:
    logger.critical(f"Erro inesperado e grave ao configurar a API Key: {e}", exc_info=True)
    st.error(f"Erro grave ao configurar a API Key: {e}. O aplicativo não pode continuar.")
    st.stop()

# --- Bloco 4: Configuração do Modelo Gemini ---
generation_config = {
    "temperature": 0.7, "top_p": 0.95, "top_k": 40, "max_output_tokens": 800,
}
safety_settings = [
    {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
]

# --- Bloco 6: Definições de Segurança (CVV) e Detecção de Risco ---
keywords_risco_originais = [
    "me matar", "me mate", "suicidio", "suicídio", "não aguento mais viver", "quero morrer",
    "queria morrer", "quero sumir", "desistir de tudo", "acabar com tudo", "fazer mal a mim",
    "me cortar", "me machucar", "automutilação", "quero me jogar", "tirar minha vida",
    "sem esperança", "fim da linha"
]
keywords_risco_regex = [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in keywords_risco_originais]
logger.info(f"{len(keywords_risco_regex)} padrões de regex para detecção de risco compilados.")
resposta_risco_padrao = (
    "Sinto muito que você esteja passando por um momento tão difícil e pensando nisso. "
    "É muito importante buscar ajuda profissional **imediatamente**. Por favor, entre em contato com o "
    "**CVV (Centro de Valorização da Vida) ligando para o número 188**. A ligação é gratuita "
    "e eles estão disponíveis 24 horas por dia para conversar com você de forma sigilosa e segura. "
    "Você não está sozinho(a) e há pessoas prontas para te ouvir e ajudar. Por favor, ligue para eles agora."
)

# --- Bloco 7: Função para Inicializar o Modelo ---
@st.cache_resource
def init_model(instruction: str):
    if instruction == DEFAULT_SYSTEM_INSTRUCTION:
        logger.warning(f"Inicializando modelo com instrução de sistema DE FALLBACK.")
    else:
        logger.info(f"Inicializando modelo com system prompt personalizado de {len(instruction)} caracteres.")
    try:
        model_instance = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction=instruction
        )
        return model_instance
    except Exception as e_model:
        logger.critical(f"Erro GRAVE ao carregar o modelo de IA: {e_model}", exc_info=True)
        st.error(f"Erro grave ao carregar o modelo de IA. O aplicativo não pode continuar. Detalhe: {e_model}")
        st.stop()

model = init_model(system_instruction_aura)

# --- Bloco 8: Gerenciamento do Histórico e Botão de Reset ---
if SESSION_MESSAGES_KEY in st.session_state and len(st.session_state[SESSION_MESSAGES_KEY]) > 1:
    if st.sidebar.button("🧹 Limpar Conversa Atual"):
        st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": "Olá! Sou Aura. Como você está se sentindo hoje? (Conversa reiniciada)"}]
        if SESSION_CHAT_KEY in st.session_state: del st.session_state[SESSION_CHAT_KEY]
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False
        logger.info("Histórico da conversa e sessão do Gemini reiniciados pelo usuário.")
        st.rerun()

if SESSION_MESSAGES_KEY not in st.session_state:
    initial_message = "Olá! Sou Aura. Como você está se sentindo hoje?"
    if critical_error_loading_prompt:
        initial_message = (
            "Olá! Sou Aura. Parece que tive um problema ao carregar minha configuração completa de personalidade. "
            "Vou tentar te ajudar da melhor forma possível com uma configuração básica, mas peço desculpas se minha interação não for a ideal. "
            "Como você está se sentindo hoje?"
        )
    st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": initial_message}]
    logger.info(f"Histórico de mensagens inicializado. Erro crítico no prompt: {critical_error_loading_prompt}")
    st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False

# --- Bloco 9: Exibição do Histórico ---
for message in st.session_state[SESSION_MESSAGES_KEY]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Bloco 10: Função para Enviar Mensagem e Processar Resposta ---
def send_message_to_aura(user_prompt: str):
    st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": user_prompt})
    with st.chat_message("user"): st.markdown(user_prompt)

    bot_response_final = ""
    try:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response_stream = ""
            
            if SESSION_CHAT_KEY not in st.session_state:
                history_for_model = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                                     for m in st.session_state[SESSION_MESSAGES_KEY][:-1]]
                st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=history_for_model)
                logger.info(f"Nova sessão de chat do Gemini iniciada com {len(history_for_model)} msgs de histórico.")

            with st.spinner("Aura está pensando... 💬"):
                response_stream = st.session_state[SESSION_CHAT_KEY].send_message(user_prompt, stream=True)

            last_chunk = None
            for chunk in response_stream:
                last_chunk = chunk
                if chunk.parts:
                    for part in chunk.parts: full_response_stream += part.text
                elif hasattr(chunk, 'text') and chunk.text: full_response_stream += chunk.text
                message_placeholder.markdown(full_response_stream + "▌")

                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    logger.warning(f"Resposta parcialmente gerada e bloqueada: {chunk.prompt_feedback.block_reason}")
                    full_response_stream += f"\n\n*(Resposta interrompida por diretrizes de segurança.)*"
                    message_placeholder.warning(full_response_stream.strip())
                    break
            
            bot_response_final = full_response_stream.strip()
            if not (last_chunk and last_chunk.prompt_feedback and last_chunk.prompt_feedback.block_reason):
                message_placeholder.markdown(bot_response_final) # Remove cursor se não bloqueado

            is_blocked_final = last_chunk and last_chunk.prompt_feedback and last_chunk.prompt_feedback.block_reason
            if is_blocked_final and not bot_response_final: # Totalmente bloqueado sem texto
                reason = f"{last_chunk.prompt_feedback.block_reason}"
                logger.error(f"Prompt bloqueado: {reason}")
                bot_response_final = f"Sua mensagem não pôde ser processada ({reason}). Tente reformular."
                message_placeholder.error(bot_response_final)
            elif not bot_response_final and not is_blocked_final: # Genuinamente vazio
                logger.warning(f"Resposta vazia da IA para: '{user_prompt}'. Usando fallback.")
                bot_response_final = "Sinto muito, não consegui pensar em uma resposta. Poderia reformular?"
                message_placeholder.markdown(bot_response_final)

        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": bot_response_final})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False

    except genai.types.BlockedPromptException as bpe:
        logger.error(f"BlockedPromptException: {bpe}", exc_info=True)
        err_msg = "Sua mensagem foi bloqueada por diretrizes de segurança. Por favor, reformule."
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": err_msg})
        with st.chat_message("assistant"): st.error(err_msg)
    except Exception as e:
        logger.error(f"Falha ao enviar/processar mensagem: {e}", exc_info=True)
        err_msg = "Desculpe, ocorreu um problema técnico. Tente novamente. 😔"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": err_msg})
        with st.chat_message("assistant"): st.markdown(err_msg)

# --- Bloco 11: Input e Lógica Principal ---
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    logger.info(f"Usuário: '{prompt[:50]}...'")
    if any(regex.search(prompt) for regex in keywords_risco_regex):
        logger.warning(f"RISCO DETECTADO: '{prompt}'")
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            st.warning("**Importante: Se você pensa em se machucar, busque ajuda profissional imediatamente.**")
            st.markdown(resposta_risco_padrao)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": resposta_risco_padrao})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False
    else:
        send_message_to_aura(prompt)

# --- Bloco 12: Coleta de Feedback ---
if len(st.session_state[SESSION_MESSAGES_KEY]) > 1 and st.session_state[SESSION_MESSAGES_KEY][-1]["role"] == "assistant":
    last_msg = st.session_state[SESSION_MESSAGES_KEY][-1]["content"]
    is_system_msg = any(keyword in last_msg for keyword in [resposta_risco_padrao, "problema técnico", "mensagem foi bloqueada", "não consegui pensar"])
    if not is_system_msg and not st.session_state.get(SESSION_FEEDBACK_SUBMITTED_KEY, False):
        st.divider()
        cols_fb = st.columns([0.6, 0.2, 0.2], gap="small")
        with cols_fb[0]: st.markdown("<div style='padding-top:0.5em;'>Essa resposta foi útil?</div>", unsafe_allow_html=True)
        if cols_fb[1].button("👍", key="fb_pos", help="Sim!"):
            logger.info(f"Feedback Positivo para: '{last_msg[:70]}...'")
            st.toast("Obrigado! 😊", icon="💖"); st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True; st.rerun()
        if cols_fb[2].button("👎", key="fb_neg", help="Não."):
            logger.info(f"Feedback Negativo para: '{last_msg[:70]}...'")
            st.toast("Obrigado pelo feedback! 🙏", icon="💡"); st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True; st.rerun()

# --- Bloco 13: Recursos Adicionais (Sidebar) ---
with st.sidebar:
    st.markdown("---"); st.subheader("Recursos Úteis 💡")
    with st.expander("Apoio e Crise:", expanded=False):
        st.markdown("- **CVV (188):** Ligação gratuita, 24h.\n- **CAPS:** Procure no SUS.")
    with st.expander("Bem-Estar Rápido:", expanded=False):
        st.markdown("* Respire fundo.\n* Movimente-se.\n* Conecte-se com alguém.")

# --- Bloco 14: Rodapé ---
st.divider()
st.caption("Aura é uma IA, não terapeuta. Em emergências, ligue CVV (188) ou procure ajuda profissional.")
debug_logger.info("FIM DA EXECUÇÃO DO SCRIPT.")
# --- Fim ---
