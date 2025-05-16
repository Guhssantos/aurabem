# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import time
import re
import logging

# --- Bloco de Configuração Inicial ---
# Configuração do Logging (Melhorado e mais detalhado)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler()  # Exibe logs no console
        # Considerar adicionar FileHandler para persistir logs em produção
        # logging.FileHandler("aura_app.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# --- Constantes para Session State (NOVO) ---
SESSION_MESSAGES_KEY = "aura_messages"
SESSION_CHAT_KEY = "aura_chat_session"
SESSION_FEEDBACK_SUBMITTED_KEY = "aura_feedback_submitted"

# --- Bloco 1: Configuração da Página ---
st.set_page_config(
    page_title="Aura - Chatbot de Apoio",
    page_icon="💖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Bloco 2: Título e Descrição ---
st.title("💖 Aura: Seu Companheiro Virtual")
st.caption("Um espaço seguro para conversar e encontrar acolhimento. Lembre-se, sou uma IA e não posso substituir um terapeuta profissional.")
st.divider()

# --- Bloco 3: Configuração da API Key e System Instruction ---
SYSTEM_PROMPT_FILE = "system_prompt_aura.txt"
system_instruction_aura = "" # Inicializa a variável

try:
    with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
        system_instruction_aura = f.read()
    logger.info(f"Instrução do sistema '{SYSTEM_PROMPT_FILE}' carregada com sucesso.")
except FileNotFoundError:
    logger.error(f"Arquivo de instrução do sistema '{SYSTEM_PROMPT_FILE}' não encontrado! Usando um fallback.")
    st.error(f"Erro Crítico: O arquivo de configuração da personalidade da Aura ({SYSTEM_PROMPT_FILE}) não foi encontrado. A Aura pode não funcionar como esperado.")
    system_instruction_aura = "Você é um chatbot de apoio. Seja gentil e prestativo. Avise que não é um terapeuta e que não pode dar conselhos médicos."
except Exception as e:
    logger.error(f"Erro ao carregar instrução do sistema '{SYSTEM_PROMPT_FILE}': {e}", exc_info=True)
    st.error(f"Erro ao carregar a personalidade da Aura: {e}. Usando fallback.")
    system_instruction_aura = "Falha ao carregar personalidade. Por favor, avise o desenvolvedor. Sou um chatbot de apoio, seja gentil."

# Configuração da API Key do Google
try:
    GOOGLE_API_KEY_APP = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY_APP)
    logger.info("Chave API do Google configurada com sucesso via Streamlit Secrets.")
except KeyError:
    logger.error("Chave API do Google (GOOGLE_API_KEY) não encontrada nos Secrets do Streamlit.")
    st.error("Ops! Parece que a Chave API do Google não foi configurada nos 'Secrets' do Streamlit. Peça ajuda para configurá-la nas definições do app.")
    st.stop()
except Exception as e:
    logger.error(f"Erro inesperado ao configurar a API Key: {e}", exc_info=True)
    st.error(f"Erro inesperado ao configurar a API Key: {e}")
    st.stop()

# --- Bloco 4: Configuração do Modelo Gemini (MELHORIA) ---
generation_config = {
    "temperature": 0.7,  # Ligeiramente reduzida para respostas mais focadas e consistentes
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 800, # Aumentado um pouco para permitir respostas mais elaboradas se necessário
}
safety_settings = [
    {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
    for c in [
        "HARM_CATEGORY_HARASSMENT",
        "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "HARM_CATEGORY_DANGEROUS_CONTENT",
    ]
]

# --- Bloco 5: (System Instruction já carregada no Bloco 3) ---

# --- Bloco 6: Definições de Segurança (CVV) e Detecção de Risco Melhorada ---
keywords_risco_originais = [
    "me matar", "me mate", "suicidio", "suicídio",
    "não aguento mais viver", "quero morrer", "queria morrer",
    "quero sumir", "desistir de tudo", "acabar com tudo",
    "fazer mal a mim", "me cortar", "me machucar", "automutilação",
    "quero me jogar", "tirar minha vida", "sem esperança", "fim da linha"
]
keywords_risco_regex = [
    re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
    for keyword in keywords_risco_originais
]
logger.info(f"{len(keywords_risco_regex)} padrões de regex para detecção de risco compilados.")

resposta_risco_padrao = (
    "Sinto muito que você esteja passando por um momento tão difícil e pensando nisso. "
    "É muito importante buscar ajuda profissional **imediatamente**. Por favor, entre em contato com o "
    "**CVV (Centro de Valorização da Vida) ligando para o número 188**. A ligação é gratuita "
    "e eles estão disponíveis 24 horas por dia para conversar com você de forma sigilosa e segura. "
    "Você não está sozinho(a) e há pessoas prontas para te ouvir e ajudar. Por favor, ligue para eles agora."
)

# --- Bloco 7: Função para Inicializar o Modelo ---
@st.cache_resource # Guarda o modelo na memória
def init_model(system_instruction_param: str):
    try:
        # MELHORIA: Usando gemini-1.5-flash-latest
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction=system_instruction_param
        )
        logger.info(f"Modelo Generativo Gemini (gemini-1.5-flash-latest) inicializado com sucesso com system prompt de {len(system_instruction_param)} caracteres.")
        return model
    except Exception as e:
        logger.critical(f"Erro GRAVE ao carregar o modelo de IA: {e}", exc_info=True)
        st.error(f"Erro grave ao carregar o modelo de IA. O aplicativo não pode continuar. Detalhe: {e}")
        st.stop()

model = init_model(system_instruction_aura)

# --- Bloco 8: Gerenciamento do Histórico da Conversa e Botão de Reset ---
if SESSION_MESSAGES_KEY in st.session_state and len(st.session_state[SESSION_MESSAGES_KEY]) > 1:
    if st.sidebar.button("🧹 Limpar Conversa Atual"): # Movido para a sidebar para menos intrusão
        st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": "Olá! Sou Aura. Como você está se sentindo hoje? (Conversa reiniciada)"}]
        if SESSION_CHAT_KEY in st.session_state:
            del st.session_state[SESSION_CHAT_KEY] # Deleta a sessão antiga para forçar recriação
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False # Reseta o feedback
        logger.info("Histórico da conversa e sessão do Gemini reiniciados pelo usuário.")
        st.rerun()

if SESSION_MESSAGES_KEY not in st.session_state:
    st.session_state[SESSION_MESSAGES_KEY] = [{"role": "assistant", "content": "Olá! Sou Aura. Como você está se sentindo hoje?"}]
    logger.info("Histórico de mensagens inicializado.")
    st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False


if SESSION_CHAT_KEY not in st.session_state:
    logger.info("Inicializando nova sessão de chat com Gemini (histórico será enviado na primeira mensagem).")
    # O histórico será passado no primeiro send_message da nova função
    # st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=[]) # Alterado para ser tratado na função de envio


# --- Bloco 9: Exibição do Histórico ---
for message in st.session_state[SESSION_MESSAGES_KEY]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# --- Bloco 10: Função para Enviar Mensagem e Processar Resposta com Streaming (NOVO e MELHORADO) ---
def send_message_to_aura(user_prompt: str):
    """
    Envia a mensagem do usuário para o modelo Gemini, processa a resposta com streaming
    e atualiza o histórico de mensagens.
    """
    st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    bot_response_final = ""
    try:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response_stream = ""
            with st.spinner("Aura está pensando... 💬"):
                # Inicia ou continua a sessão de chat
                # Se a sessão já existe, ela continua. Se não, start_chat é implicitamente chamado.
                # Passamos o histórico das mensagens do app para o modelo, exceto a última (que é a do assistant placeholder)
                # O Gemini SDK gerencia o histórico interno da sessão, mas é bom ser explícito ao enviar a mensagem.
                current_chat_history_for_model = []
                for msg in st.session_state[SESSION_MESSAGES_KEY][:-1]: # Exclui o placeholder do assistant
                    # Gemini espera 'parts' como uma lista de strings, e o role 'model' para o assistente
                    role_for_gemini = "user" if msg["role"] == "user" else "model"
                    current_chat_history_for_model.append({"role": role_for_gemini, "parts": [msg["content"]]})

                if SESSION_CHAT_KEY not in st.session_state:
                    st.session_state[SESSION_CHAT_KEY] = model.start_chat(history=current_chat_history_for_model)
                    logger.info("Nova sessão de chat do Gemini iniciada com histórico.")

                # Envia a mensagem do usuário atual para a sessão de chat existente
                response_stream = st.session_state[SESSION_CHAT_KEY].send_message(user_prompt, stream=True)


            for chunk in response_stream:
                if chunk.parts: # Gemini 1.5 Flash usa 'parts'
                    for part in chunk.parts:
                        full_response_stream += part.text
                        message_placeholder.markdown(full_response_stream + "▌")
                elif hasattr(chunk, 'text') and chunk.text: # Para compatibilidade ou outros modelos
                    full_response_stream += chunk.text
                    message_placeholder.markdown(full_response_stream + "▌")

                # Checagem de bloqueio por segurança no meio do stream
                if chunk.prompt_feedback and chunk.prompt_feedback.block_reason:
                    logger.warning(f"Resposta parcialmente gerada e bloqueada por segurança: {chunk.prompt_feedback.block_reason}")
                    full_response_stream += f"\n\n(Conteúdo removido por diretrizes de segurança: {chunk.prompt_feedback.block_reason_message})"
                    message_placeholder.warning(full_response_stream.strip())
                    break # Sai do loop de streaming

            if not full_response_stream.strip() and not (response_stream.prompt_feedback and response_stream.prompt_feedback.block_reason):
                logger.warning(f"Resposta vazia da IA para o prompt: '{user_prompt}'. Retornando fallback.")
                bot_response_final = "Sinto muito, não consegui pensar em uma resposta clara para isso no momento. Você poderia tentar reformular sua pergunta ou falar sobre outra coisa?"
                message_placeholder.markdown(bot_response_final)
            else:
                bot_response_final = full_response_stream.strip()
                message_placeholder.markdown(bot_response_final)

            # Checagem final de bloqueio (caso nenhum texto tenha sido gerado)
            if not bot_response_final and hasattr(response_stream, 'prompt_feedback') and response_stream.prompt_feedback.block_reason:
                block_reason = response_stream.prompt_feedback.block_reason
                block_message = response_stream.prompt_feedback.block_reason_message if hasattr(response_stream.prompt_feedback, 'block_reason_message') else "Motivo não especificado."
                logger.error(f"Prompt bloqueado pela API Gemini. Razão: {block_reason}. Mensagem: {block_message}")
                bot_response_final = f"Sinto muito, sua mensagem não pôde ser processada devido às diretrizes de conteúdo ({block_reason}). Tente reformular, por favor."
                message_placeholder.error(bot_response_final)


        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": bot_response_final})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False # Permite novo feedback

    except genai.types.BlockedPromptException as bpe:
        logger.error(f"Prompt bloqueado pela API Gemini (BlockedPromptException): {bpe}", exc_info=True)
        error_msg_user = "Sua mensagem foi bloqueada por nossas diretrizes de segurança. Por favor, reformule sua pergunta."
        st.error(error_msg_user)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_msg_user})
    except Exception as e:
        error_msg_user = "Desculpe, ocorreu um problema técnico ao processar sua mensagem. Tente novamente mais tarde ou, se o problema persistir, avise o mantenedor do aplicativo."
        logger.error(f"Falha ao enviar mensagem para o Gemini ou processar resposta: {e}", exc_info=True)
        st.error(error_msg_user)
        error_response_for_history = "Sinto muito, tive um problema técnico interno e não consegui responder. 😔"
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": error_response_for_history})
        # O placeholder já terá sumido ou o erro já foi mostrado
        with st.chat_message("assistant"):
            st.markdown(error_response_for_history)


# --- Bloco 11: Input e Lógica Principal ---
if prompt := st.chat_input("Digite sua mensagem aqui..."):
    logger.info(f"Usuário enviou: '{prompt[:50]}...' (tamanho: {len(prompt)})") # Loga o início do prompt

    contem_risco = any(regex.search(prompt) for regex in keywords_risco_regex)

    if contem_risco:
        logger.warning(f"Detectada palavra/expressão de RISCO na mensagem do usuário: '{prompt}'")
        with st.chat_message("assistant"):
            st.warning("**Importante: Se você está pensando em se machucar ou sente que está em perigo, por favor, busque ajuda profissional imediatamente.**")
            st.markdown(resposta_risco_padrao)
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "user", "content": prompt}) # Adiciona msg do user ao histórico
        st.session_state[SESSION_MESSAGES_KEY].append({"role": "assistant", "content": resposta_risco_padrao})
        st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = False # Permite novo feedback
    else:
        send_message_to_aura(prompt)

# --- Bloco 12: Coleta de Feedback (NOVO) ---
if len(st.session_state[SESSION_MESSAGES_KEY]) > 1 and st.session_state[SESSION_MESSAGES_KEY][-1]["role"] == "assistant":
    if not st.session_state.get(SESSION_FEEDBACK_SUBMITTED_KEY, False): # Verifica se o feedback já foi dado para a última resposta
        st.divider()
        cols = st.columns(8)
        cols[0].write("Essa resposta foi útil?")
        if cols[1].button("👍", key="feedback_positivo"):
            logger.info("Feedback da conversa: Positivo (👍)")
            st.toast("Obrigado pelo seu feedback! 😊", icon="💖")
            st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True
            st.rerun() # Para remover os botões de feedback
        if cols[2].button("👎", key="feedback_negativo"):
            logger.info("Feedback da conversa: Negativo (👎)")
            st.toast("Obrigado pelo seu feedback. Vamos continuar melhorando! 🙏", icon="💡")
            st.session_state[SESSION_FEEDBACK_SUBMITTED_KEY] = True
            st.rerun() # Para remover os botões de feedback


# --- Bloco 13: Recursos Adicionais (NOVO - Exemplo) ---
with st.sidebar: # Movido para a sidebar
    st.markdown("---")
    st.subheader("Recursos Úteis 💡")
    with st.expander("Para momentos de crise ou necessidade de apoio:", expanded=False):
        st.markdown("- **CVV (Centro de Valorização da Vida):** Disque **188** (ligação gratuita, 24h).")
        st.markdown("- **SUS:** Procure um CAPS (Centro de Atenção Psicossocial) perto de você.")
        st.markdown("- Lembre-se: Você não está sozinho(a). Buscar ajuda é um ato de coragem.")

    with st.expander("Dicas rápidas de bem-estar:", expanded=False):
        st.markdown("""
        *   **Pausa e Respire:** Tire alguns minutos para respirar profundamente. Inspire pelo nariz contando até 4, segure por 4 e expire pela boca contando até 6.
        *   **Movimente-se:** Uma caminhada leve ou alguns alongamentos podem ajudar a aliviar a tensão.
        *   **Conecte-se:** Converse com um amigo, familiar ou alguém de confiança.
        *   **Pequenos Prazeres:** Ouça uma música que você gosta, assista a algo leve, leia um trecho de um livro.
        *(Lembre-se, estas são sugestões simples e não substituem o acompanhamento profissional.)*
        """)


# --- Bloco 14: Rodapé ---
st.divider()
st.caption(
    "Aura é uma Inteligência Artificial e suas respostas são geradas por um modelo de linguagem. "
    "Ela **não é uma terapeuta** e não substitui o acompanhamento psicológico ou psiquiátrico profissional. "
    "Em caso de emergência, sofrimento intenso ou necessidade de apoio especializado, **ligue para o CVV (188)** ou procure um profissional de saúde mental. "
    "Sua privacidade é importante. As conversas podem ser registradas anonimamente para fins de melhoria do sistema."
)

# --- Fim do app.py ---