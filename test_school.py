import os

from eventsourcing.utils.random import encode_random_bytes

from school import Course, School, SchoolApplication, Student


def test():

    # Keep this safe.
    cipher_key = encode_random_bytes(num_bytes=32)
    os.environ["CIPHER_KEY"] = cipher_key

    app = SchoolApplication()

    # start with creating our school
    school_id = app.open_school(name="International University")

    # change school's name
    school = app.repository[school_id]
    assert isinstance(school, School)
    app.change_school_name(school_id=school_id, name="National U")

    # check that school's list of courses is empty
    assert app.get_course_list(school_id) == ()

    # make sure that name changed event is in history
    school = app.repository[school_id]
    assert school.__version__ == 1
    assert isinstance(school.history[0], School.AttributeChanged)
    assert school.history[0].value == "National U"

    # create two courses
    first_course = Course.__create__(title="Geography 1")
    second_course = Course.__create__(title="Physics")
    app.add_course_to_school(school_id, first_course)
    app.add_course_to_school(school_id, second_course)
    assert app.get_course_list(school_id) == ("Geography 1", "Physics")

    # make sure courses are in history
    school = app.repository[school_id]
    assert isinstance(school._history[1], School.CourseAdded)
    assert (
        app.repository[school_id]._history[1].timestamp
        <= app.repository[school_id]._history[2].timestamp
    )
    assert app.repository[school_id].history[1].course.id == first_course.id

    # change a course title
    app.change_course_title(second_course, app.repository[school_id], "Physics 2")
    assert app.get_course_list(school_id) == ("Geography 1", "Physics 2")

    # remove a course that doesn't exist - this should cause a ValueError
    third_course = Course.__create__(title="World History")
    try:
        app.remove_course_from_school(school_id, third_course)
    except ValueError:
        pass
    else:
        raise Exception("Should not get here")

    # remove a course
    app.remove_course_from_school(school_id, second_course)
    school = app.repository[school_id]
    assert isinstance(school.history[3], School.CourseRemoved)
    assert school.history[3].course == second_course
    assert school.history[3].course.title == "Physics 2"
    assert len(school.history) == 4

    # create a student and enroll them in a course
    student = Student.__create__(full_name="George Jetson")
    app.enroll_student_in_course(school_id, first_course, student)
    school = app.repository[school_id]
    assert isinstance(school.history[4], School.StudentEnrolled)

    # withdraw a student from a course
    app.withdraw_student_from_course(school_id, first_course, student)
    school = app.repository[school_id]
    assert isinstance(school.history[5], School.StudentWithdrawn)
    assert school.history[5].student.full_name == "George Jetson"

    # withdraw a student from a course they were not enrolled in
    # this should fail
    try:
        app.withdraw_student_from_course(school_id, third_course, student)
    except ValueError:
        pass
    else:
        raise Exception("Should not get here")
    assert len(school.history) == 6

    # Check projection for correct list of courses
    assert app.get_course_list(school_id) == ("Geography 1",)

    # discard school
    school.__discard__()
    assert len(school.__pending_events__) == 1
    assert isinstance(school.__pending_events__[0], School.Discarded)


if __name__ == "__main__":
    test()
