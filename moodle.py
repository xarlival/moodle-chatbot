from datetime import datetime, timedelta
from logging import Logger
from typing import List

import requests
import os

from telegram.ext import ContextTypes


class Moodle:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self.logger.info('Starting Moodle')
        self.endpoint = ('{}{}?moodlewsrestformat={}'
                         .format(os.getenv('MOODLE_URL'), os.getenv('WS_PATH'), os.getenv('REST_FORMAT')))

        moodle_token = self.get_token(os.getenv('REST_USERNAME'), os.getenv('REST_PASSWORD'))
        self.endpoint = self.endpoint + '&wstoken={}'.format(moodle_token)
        self.date_format = '%d/%m/%y'
        self.datetime_format = '%d/%m/%y %H:%M'
        self.logger.info('Moodle started successfully: Moodle REST token obtained')

    def get_token(self, username: str, password: str) -> str:
        login_endpoint = ('{}{}?username={}&password={}&service={}'.format(os.getenv('MOODLE_URL'),
                                                                           os.getenv('LOGIN_PATH'),
                                                                           username,
                                                                           password,
                                                                           os.getenv('WS_SERVICE')))
        response = requests.get(login_endpoint)
        return response.json()['token']

    def get_user_info(self, username: str) -> dict:
        moodle_ws_function = 'core_user_get_users_by_field'
        params = f'&wsfunction={moodle_ws_function}&field=username&values[0]={username}'
        response = requests.get(self.endpoint + params)
        return response.json()[0] if 'exception' not in response.json() and len(response.json()) > 0 else None

    def get_courses(self, userid: str) -> dict:
        moodle_ws_function = 'core_enrol_get_users_courses'
        params = f'&wsfunction={moodle_ws_function}&userid={userid}'
        response = requests.get(self.endpoint + params)
        return response.json()

    def get_course_grades(self, userid: str) -> List[dict]:
        moodle_ws_function = 'gradereport_overview_get_course_grades'
        params = f'&wsfunction={moodle_ws_function}&userid={userid}'
        response = requests.get(self.endpoint + params)
        return response.json()['grades']

    def get_assignments(self, courseids: [str]) -> dict:
        moodle_ws_function = 'mod_assign_get_assignments'
        params = f'&wsfunction={moodle_ws_function}'
        for i, courseid in enumerate(courseids):
            params = params + f'&courseids[{i}]={courseid}&includenotenrolledcourses=1'
        response = requests.get(self.endpoint + params)
        return response.json()

    def is_assignment_submitted(self, userid: str, assignid: str) -> bool:
        moodle_ws_function = 'mod_assign_get_submission_status'
        params = f'&wsfunction={moodle_ws_function}&userid={userid}&assignid={assignid}'
        response = requests.get(self.endpoint + params)

        if ('lastattempt' in response.json()
                and 'submission' in response.json()['lastattempt']
                and 'status' in response.json()['lastattempt']['submission']):
            return True if response.json()['lastattempt']['submission']['status'] == 'submitted' else False
        else:
            return False

    def get_assignment_grades(self, assignids: [str]) -> List[dict]:
        moodle_ws_function = 'mod_assign_get_grades'
        params = f'&wsfunction={moodle_ws_function}'
        for i, assignid in enumerate(assignids):
            params = params + f'&assignmentids[{i}]={assignid}'
        response = requests.get(self.endpoint + params)
        return response.json()['assignments']

    def get_quizzes(self, courseids: [str]) -> List[dict]:
        moodle_ws_function = 'mod_quiz_get_quizzes_by_courses'
        params = f'&wsfunction={moodle_ws_function}'
        for i, courseid in enumerate(courseids):
            params = params + f'&courseids[{i}]={courseid}'
        response = requests.get(self.endpoint + params)
        return response.json()['quizzes']

    def get_quizz_best_grade(self, userid: str, quizid: str) -> dict:
        moodle_ws_function = 'mod_quiz_get_user_best_grade'
        params = f'&wsfunction={moodle_ws_function}&quizid={quizid}&userid={userid}'
        response = requests.get(self.endpoint + params)
        return response.json()

    def get_calendar_events(self, courseids: [str], timestart: float, timeend: float) -> List[dict]:
        moodle_ws_function = 'core_calendar_get_calendar_events'
        params = f'&wsfunction={moodle_ws_function}&options[timestart]={timestart}&options[timeend]={timeend}'
        for i, courseid in enumerate(courseids):
            params = params + f'&events[courseids][{i}]={courseid}'
        response = requests.get(self.endpoint + params)
        return response.json()['events']

    def get_pending_messages_and_notifications(self, userid: str) -> List[dict]:
        moodle_ws_function = 'core_message_get_messages'
        params = f'&wsfunction={moodle_ws_function}&useridto={userid}&read=0'
        response = requests.get(self.endpoint + params)
        return response.json()['messages']

    def login(self, username, context: ContextTypes.DEFAULT_TYPE) -> bool:
        user_info = self.get_user_info(username)

        if user_info:
            context.user_data['userid'] = user_info['id']
            context.user_data['user_name'] = user_info['firstname']
            return True
        else:
            return False

    def prepare_user_info(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        courses = self.get_courses(context.user_data['userid'])
        context.user_data['courseids'] = [course['id'] for course in courses]
        context.user_data['course_names'] = [course['fullname'] for course in courses]

    def course_grades(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        grades = self.get_course_grades(context.user_data['userid'])

        response = "Las clasificaciones de tus asignaturas son:"

        for grade in grades:
            courseid = int(grade['courseid'])
            course_name = context.user_data['course_names'][context.user_data['courseids'].index(courseid)]

            if grade['grade'] != '-':
                grade_value = float(grade['grade'].replace(",", ".")) / 10
            else:
                grade_value = 'Sin clasificar'
            response += '\n• {}: {}'.format(course_name, grade_value)

        return response

    def pending_assignments(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        assignment_courses = self.get_assignments(context.user_data['courseids'])
        response = ''

        if assignment_courses['courses']:
            for course in assignment_courses['courses']:
                course['assignments'] = [assignment for assignment in course['assignments'] if
                                         not self.is_assignment_submitted(context.user_data['userid'], assignment['id'])
                                         and datetime.fromtimestamp(assignment['duedate']) > datetime.now()]

            for course in assignment_courses['courses']:
                if course['assignments']:
                    response += ('\nEn la asignatura {} tienes pendientes de entregar las tareas:'
                                 .format(course['fullname']))
                    for assignment in course['assignments']:
                        duedate = datetime.fromtimestamp(assignment['duedate'])
                        response += ('\n• {}. Fecha límite: {}'
                                     .format(assignment['name'], duedate.strftime(self.date_format)))
                    response += '\n'

        return response

    def assignment_grades(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        assignment_courses = self.get_assignments(context.user_data['courseids'])
        submitted_assignments = []
        response = ''

        if assignment_courses['courses']:
            for course in assignment_courses['courses']:
                submitted_assignments.extend([assignment['id'] for assignment in course['assignments'] if
                                              self.is_assignment_submitted(context.user_data['userid'],
                                                                           assignment['id'])])

        assign_grades = self.get_assignment_grades(submitted_assignments)
        assignment_graded_ids = [assignment['assignmentid'] for assignment in assign_grades]

        for course in assignment_courses['courses']:
            course['assignments'] = [assignment for assignment in course['assignments'] if
                                     assignment['id'] in assignment_graded_ids]

        for course in assignment_courses['courses']:
            if course['assignments']:
                response += '\nEn la asignatura {} tienes las siguientes tareas clasificadas:'.format(
                    course['fullname'])

                for assignment in course['assignments']:
                    grade = next((grade for grade in assign_grades if grade['assignmentid'] == assignment['id']), None)
                    grade_value = float(grade['grades'][0]['grade'].replace(",", ".")) / 10
                    response += "\n• {}: {}".format(assignment['name'], grade_value)

        return response

    def pending_quizzes(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        quizzes = [quizz for quizz in self.get_quizzes(context.user_data['courseids']) if
                   not self.get_quizz_best_grade(context.user_data['userid'], quizz['id'])['hasgrade']]
        courses = {}
        response = ''

        for quizz in quizzes:
            if quizz['timeclose'] == 0 or (datetime.fromtimestamp(quizz['timeclose']) > datetime.now()):
                if quizz['course'] not in courses:
                    courses[quizz['course']] = []
                courses[quizz['course']].append(quizz)

        for courseid, course_pending_quizzes in courses.items():
            course_name = context.user_data['course_names'][context.user_data['courseids'].index(courseid)]
            response += '\nEn la asignatura {} tienes los siguientes cuestionarios pendientes:'.format(course_name)

            for quizz in course_pending_quizzes:
                response += "\n• {}. ".format(quizz['name'])

                if quizz['timeclose'] != 0:
                    duedate = datetime.fromtimestamp(quizz['timeclose'])
                    response += "Fecha límite: {}".format(duedate.strftime(self.date_format))
                else:
                    response += "Sin fecha límite."

        return response

    def next_week_events(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        timestart = int(datetime.now().timestamp())
        timeend = int((datetime.now() + timedelta(days=7)).timestamp())
        events = self.get_calendar_events(context.user_data['courseids'], timestart, timeend)
        sorted_events = sorted(events, key=lambda x: x['timestart'])
        response = 'En la próxima semana tienes los siguientes eventos:'

        for event in sorted_events:
            duedate = datetime.fromtimestamp(event['timestart'])
            response += '\n• {}: finaliza el {}'.format(event['name'], duedate.strftime(self.date_format))

        return response

    def user_pending_messages(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        messages = self.get_pending_messages_and_notifications(context.user_data['userid'])
        messages = [message for message in messages if message['notification'] == 0]

        if len(messages) == 0:
            response = 'No tienes mensajes sin leer'

        else:
            sorted_messages = sorted(messages, key=lambda x: x['timecreated'])
            response = 'Tienes los siguientes mensajes sin leer:'

            for message in sorted_messages:
                date = datetime.fromtimestamp(message['timecreated']).strftime(self.datetime_format)
                response += '\n• {} [{}]: "{}".'.format(message['userfromfullname'], date, message['smallmessage'])

        return response

    def user_pending_notifications(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        messages = self.get_pending_messages_and_notifications(context.user_data['userid'])
        messages = [message for message in messages if message['notification'] == 1]

        if len(messages) == 0:
            response = 'No tienes notificaciones sin leer'

        else:
            response = 'Tienes las siguientes notificaciones sin leer:'

            for message in messages:
                date = datetime.fromtimestamp(message['timecreated']).strftime(self.datetime_format)
                response += '\n• [{}] {}.'.format(date, message['smallmessage'])

        return response
