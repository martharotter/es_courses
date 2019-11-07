from uuid import UUID, uuid4, uuid5

from eventsourcing.application.sqlalchemy import SQLAlchemyApplication
from eventsourcing.domain.model.aggregate import BaseAggregateRoot
from eventsourcing.domain.model.collection import Collection
from eventsourcing.domain.model.decorators import attribute
from eventsourcing.domain.model.entity import VersionedEntity


SCHOOL_COURSE_COLLECTION_NS = UUID("bdae89e5-9af6-4e07-80fd-19d8adc6c2a6")


class School(BaseAggregateRoot):
    """ 
    An institute of learning. Can have courses and students enrolled in 
    those courses.
    """

    def __init__(self, name=None, **kwargs):
        super(School, self).__init__(**kwargs)
        self._history = []
        self._name = name
        self.courses = []

    @classmethod
    def open(cls, name):
        return cls.__create__(
            name=name, event_class=cls.Created
        )

    @property
    def history(self):
        return tuple(self._history)

    @attribute
    def name(self):
        """A mutable event-sourced attribute."""

    class Event(BaseAggregateRoot.Event):
        pass

    class Created(Event, BaseAggregateRoot.Created):
        """Published when a school is opened."""

        @property
        def school_id(self):
            return self.__dict__["originator_id"]

    class Discarded(Event, BaseAggregateRoot.Discarded):
        """Published when a school is closed."""

        @property
        def school_id(self):
            return self.__dict__["originator_id"]

    # Update school name command and event
    def update_name(self, name):
        self.__trigger_event__(School.AttributeChanged, value=name, name="_name")

    class AttributeChanged(Event, BaseAggregateRoot.AttributeChanged):
        """Published when a school changes its name."""

        def mutate(self, obj):
            obj._name = self.value
            obj._history.append(self)

    # Add a course command and event
    def add_course(self, course):
        self.__trigger_event__(School.CourseAdded, course=course)

    class CourseAdded(Event):
        """Published when a course is added to a school."""

        @property
        def course(self):
            return self.__dict__["course"]

        @property
        def school_id(self):
            return self.__dict__["school_id"]

        def mutate(self, obj):
            obj.courses.append(self.course.title)
            obj._history.append(self)

    # Remove a course command and event
    def remove_course(self, course):
        """ Removes course from school """
        self.__trigger_event__(School.CourseRemoved, course=course)

    class CourseRemoved(Event):
        def mutate(self, obj):
            obj.courses.remove(self.course.title)
            obj._history.append(self)

    # Update a course title command and event
    def update_course_title(self, old_title, new_title):
        self.__trigger_event__(
            School.CourseTitleChanged, old_title=old_title, new_title=new_title
        )

    class CourseTitleChanged(Event):
        def mutate(self, obj):
            obj.courses.remove(self.old_title.title)
            obj.courses.append(self.new_title)

    # Enroll a student command and event
    def enroll_student(self, course, student):
        self.__trigger_event__(School.StudentEnrolled, course=course, student=student)

    class StudentEnrolled(Event):
        def mutate(self, obj):
            obj._history.append(self)

    # Withdraw a student command and event
    def withdraw_student(self, course, student):
        self.__trigger_event__(School.StudentWithdrawn, course=course, student=student)

    class StudentWithdrawn(Event):
        def mutate(self, obj):
            obj._history.append(self)


class Course(VersionedEntity):
    """
    An individual course at the schoool.
    """

    def __init__(self, title, *args, **kwargs):
        super(Course, self).__init__(*args, **kwargs)
        self._title = title
        self.students = []

    @attribute
    def title(self):
        """
        The title of the course (an event-sourced attribute)
        """
    class Event(VersionedEntity.Event):
        pass

    class Created(Event, VersionedEntity.Created):
        pass

    class Discarded(Event, VersionedEntity.Discarded):
        pass

    # Update a course title command and event
    def update_name(self, name):
        self.__trigger_event__(Course.AttributeChanged, value=name, name="_title")

    class AttributeChanged(Event, VersionedEntity.AttributeChanged):
        def mutate(self, obj):
            obj._title = self.value

    # Add student to course command and event
    def add_student(self, student_name):
        self.__trigger_event__(Course.StudentAdded, value=student_name)

    class StudentAdded(Event):
        def mutate(self, obj):
            obj.students.append(self.value)

    # Remove student from course command and event
    def remove_student(self, student_name):
        self.__trigger_event__(Course.StudentRemoved, value=student_name)

    class StudentRemoved(Event):
        def mutate(self, obj):
            obj.students.remove(self.value)


class Student(VersionedEntity):
    """
    A student at the school. Can enroll in one or more courses.
    """

    def __init__(self, full_name, *args, **kwargs):
        super(Student, self).__init__(*args, **kwargs)
        self.full_name = full_name

    class Event(VersionedEntity.Event):
        pass

    class Created(Event, VersionedEntity.Created):
        pass

    class Discarded(Event, VersionedEntity.Discarded):
        pass


# Test application
class SchoolApplication(SQLAlchemyApplication):
    persist_event_type = (School.Event, Course.Event, Student.Event)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def open_school(name):
        """Opens new school for courses and enrollment"""
        school = School.open(name=name)
        school.__save__()
        return school.id

    def change_school_name(self, school_id, name):
        """ Change a school's name """
        school = self.repository[school_id]
        assert isinstance(school, School)
        school.update_name(name=name)
        school.__save__()

    def get_course_list(self, school_id):
        """Returns a tuple of course names for a given school."""
        school = self.repository[school_id]
        return tuple(school.courses)

    def get_students_in_course(self, course):
        """Returns a tuple of course names for a given school."""
        return tuple(course.students)

    def add_course_to_school(self, school_id, course):
        """Add course to a school"""
        school = self.repository[school_id]
        school.add_course(course=course)
        school.__save__()

    def remove_course_from_school(self, school_id, course):
        """Remove a course from a school"""
        school = self.repository[school_id]
        school.remove_course(course=course)
        school.__save__()

    def change_course_title(self, course, school, name):
        """ Change a course's name """
        school.update_course_title(course, name)
        school.__save__()
        course.update_name(name)

    def enroll_student_in_course(self, school_id, course, student):
        """ Enroll a student in a course """
        school = self.repository[school_id]
        school.enroll_student(course, student)
        school.__save__()
        course.add_student(student.full_name)

    def withdraw_student_from_course(self, school_id, course, student):
        """ Withdraw a student in a course """
        school = self.repository[school_id]
        school.withdraw_student(course, student)
        school.__save__()
        course.remove_student(student.full_name)


def make_school_course_collection_id(
    school_id, collection_ns=SCHOOL_COURSE_COLLECTION_NS
):
    return uuid5(collection_ns, str(school_id))
