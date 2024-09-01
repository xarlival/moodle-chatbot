from openai import OpenAI


class ChatGPT:

    def __init__(self, logger) -> None:
        self.logger = logger
        self.logger.info('Starting ChatGPT')

        self.api = OpenAI()
        self.chat_gpt_context = [
            {"role": "system", "content": "Eres un asistente de un aula virtual alojado en Moodle." +
                                          "Responderás preguntas relacionadas con el aula virtual. Lo que puede " +
                                          "responder este bot son las tareas pendientes, la calificación de las " +
                                          "tareas, la calificación de los cursos, los cuestionarios pendientes, " +
                                          "mensajes pendientes, notificaciones pendientes y los eventos de la " +
                                          "próxima semana."}
        ]

        self.logger.info('ChatGPT started successfully')

    def get_response(self, user_input: str) -> str:
        self.chat_gpt_context.append({"role": "user", "content": user_input})

        response = self.api.chat.completions.create(
            messages=self.chat_gpt_context,
            model="gpt-4o-mini",
        )

        response_content = response.choices[0].message.content
        self.logger.info('Anwsering "' + response_content + '" to the input "' + user_input + '".')

        if response_content:
            self.chat_gpt_context.append({"role": "assistant", "content": response_content})

        return response_content

    def save_chat_gpt_context(self, user_input: str, bot_output: str) -> None:
        self.chat_gpt_context.append({"role": "user", "content": user_input})
        self.chat_gpt_context.append({"role": "assistant", "content": bot_output})
