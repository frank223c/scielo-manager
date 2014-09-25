# coding: utf-8
import datetime
from django.test import TestCase
from django_factory_boy import auth
from django.conf import settings
from articletrack import models
from . import modelfactories
from scielomanager.utils import misc

def create_notices(expected_error_level, checkin):
    """
    To test some checkin's actions, such as: review, accept, reject,
    is required that the checkin, return an expected error level.
    So, this function helps, creating Notices objects to retrun
    that expected checkin.get_error_level.
    """
    serv_status_count = models.SERVICE_STATUS_MAX_STAGES
    for step in xrange(0, serv_status_count):
        # SERV BEGIN
        modelfactories.NoticeFactory(
            checkin=checkin,
            stage=" ", message=" ", status="SERV_BEGIN",
            created_at=datetime.datetime.now())
        # EXPECTED NOTICE
        modelfactories.NoticeFactory(
            checkin=checkin,
            stage=" ", message=" ", status=expected_error_level,
            created_at=datetime.datetime.now())
        # SERV BEGIN
        modelfactories.NoticeFactory(
            checkin=checkin,
            stage=" ", message=" ", status="SERV_END",
            created_at=datetime.datetime.now())


class CommentTests(TestCase):

    def test_comment_ordering(self):
        ordering = models.Comment._meta.ordering
        self.assertEqual(ordering, ['created_at'])


class TicketTests(TestCase):

    def test_ticket_ordering(self):
        ordering = models.Ticket._meta.ordering
        self.assertEqual(ordering, ['started_at'])


class TeamTests(TestCase):

    def test_add_member(self):
        user = auth.UserF(is_active=True)
        team = modelfactories.TeamFactory()
        team.join(user)

        self.assertEqual(team.member.all()[0].username, user.username)


    def test_team(self):
        user = auth.UserF(is_active=True)
        team = modelfactories.TeamFactory(name=u'Team Alcachofra')
        team.join(user)
        checkin = modelfactories.CheckinFactory(submitted_by=user)

        self.assertEqual(checkin.team.all()[0].name, u'Team Alcachofra')

    def test_team_without_submitted_by_user(self):
        checkin = modelfactories.CheckinFactory()

        self.assertEqual(checkin.team, None)

    def test_team_members(self):
        user1 = auth.UserF(is_active=True)
        user2 = auth.UserF(is_active=True)
        user3 = auth.UserF(is_active=True)

        team1 = modelfactories.TeamFactory(name=u'Team Alcachofra')
        team1.join(user1)
        team1.join(user2)

        team2 = modelfactories.TeamFactory(name=u'Team Picles')
        team2.join(user2)
        team2.join(user3)

        checkin = modelfactories.CheckinFactory(submitted_by=user1)

        users = [i.username for i in checkin.team_members]

        self.assertTrue(user1.username in users)
        self.assertTrue(user2.username in users)
        self.assertFalse(user3.username in users)

class CheckinTests(TestCase):

    def setUp(self):
        self.user = auth.UserF(is_active=True)
        # Producer definition:
        group_producer = auth.GroupF(name='producer')
        self.user.groups.add(group_producer)
        self.user.save()
        # QAL 1 definitions
        self.user_qal_1 = auth.UserF(is_active=True)
        group_qal_1 = auth.GroupF(name='QAL1')
        self.user_qal_1.groups.add(group_qal_1)
        self.user_qal_1.save()
        # QAL 2 definitions
        self.user_qal_2 = auth.UserF(is_active=True)
        self.group_qal_2 = auth.GroupF(name='QAL2')
        self.user_qal_2.groups.add(self.group_qal_2)
        self.user_qal_2.save()

    def test_new_checkin_is_pending_and_clear(self):

        checkin = modelfactories.CheckinFactory()
        # rejected_* is clear
        self.assertIsNone(checkin.rejected_by)
        self.assertIsNone(checkin.rejected_at)
        self.assertIsNone(checkin.rejected_cause)
        self.assertFalse(checkin.is_rejected)
        # reviewd_* is clear
        self.assertIsNone(checkin.reviewed_by)
        self.assertIsNone(checkin.reviewed_at)
        self.assertIsNone(checkin.scielo_reviewed_by)
        self.assertIsNone(checkin.scielo_reviewed_at)
        # is_*_reviewed must be false
        self.assertFalse(checkin.is_level1_reviewed)
        self.assertFalse(checkin.is_level2_reviewed)
        self.assertFalse(checkin.is_full_reviewed)
        # accepted_* is clear
        self.assertIsNone(checkin.accepted_by)
        self.assertIsNone(checkin.accepted_at)
        # default status is pending
        self.assertEqual(checkin.status, 'pending')

    def test_reject_workflow_simple(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        rejection_text = 'your checkin is bad, and you should feel bad!'  # http://www.quickmeme.com/Zoidberg-you-should-feel-bad/?upcoming

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # can be reviewed and can be rejected, then reject
        self.assertTrue(checkin.can_be_reviewed)
        self.assertTrue(checkin.can_be_rejected)
        checkin.do_reject(self.user_qal_1, rejection_text)

        # check status and Integrity
        self.assertEqual(checkin.status, 'rejected')
        self.assertEqual(checkin.rejected_by, self.user_qal_1)
        self.assertIsNotNone(checkin.rejected_at)

        # fields related with review and accept, must be clear
        self.assertIsNone(checkin.reviewed_by)
        self.assertIsNone(checkin.reviewed_at)
        self.assertIsNone(checkin.scielo_reviewed_by)
        self.assertIsNone(checkin.scielo_reviewed_at)
        self.assertIsNone(checkin.accepted_by)
        self.assertIsNone(checkin.accepted_at)

        # the checkin is not pending, reviewed, or accepted
        self.assertFalse(checkin.is_full_reviewed)
        self.assertFalse(checkin.is_accepted)
        self.assertFalse(checkin.can_be_accepted)
        self.assertFalse(checkin.can_be_reviewed)

        # checkin must be able to be sent to pending
        self.assertTrue(checkin.can_be_send_to_pending)
        self.assertEqual(checkin.rejected_cause, rejection_text)

    def test_accept_workflow_simple(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)

        # fields related with review and accept, must be clear
        self.assertEqual(checkin.accepted_by, self.user_qal_2)
        self.assertIsNotNone(checkin.accepted_at)
        self.assertEqual(checkin.reviewed_by, self.user_qal_1)
        self.assertEqual(checkin.scielo_reviewed_by, self.user_qal_2)
        self.assertIsNotNone(checkin.reviewed_at)
        self.assertIsNotNone(checkin.scielo_reviewed_at)

        # checkin must be accepted
        self.assertTrue(checkin.is_accepted)

    def test_accept_raises_ValueError_when_already_accepted(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)

        self.assertRaises(ValueError, lambda: checkin.accept(self.user_qal_2))

    def test_accept_raises_ValueError_when_user_is_inactive(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # users
        active_user = auth.UserF(is_active=True)
        active_user.groups.add(self.group_qal_2)
        active_user.save()

        inactive_user = auth.UserF(is_active=False)
        inactive_user.groups.add(self.group_qal_2)
        inactive_user.save()

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(active_user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        self.assertRaises(ValueError, lambda: checkin.accept(inactive_user))

    def test_is_accepted_method_with_accepted_checkin(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)
        self.assertTrue(checkin.is_accepted)

    def test_is_accepted_method_without_accepted_checkin(self):
        checkin = modelfactories.CheckinFactory()
        self.assertFalse(checkin.is_accepted)

    def test_get_newest_checkin(self):
        user = auth.UserF(is_active=True)
        checkin1 = modelfactories.CheckinFactory(uploaded_at=datetime.datetime.now())

        self.assertEqual(checkin1.get_newest_checkin,
                         checkin1.article.checkins.order_by('uploaded_at')[0])

        checkin2 = modelfactories.CheckinFactory(accepted_by=user,
                                                 accepted_at=datetime.datetime.now(),
                                                 uploaded_at=datetime.datetime.now(),
                                                 status='accepted')
        self.assertEqual(checkin2.get_newest_checkin,
                         checkin2.article.checkins.order_by('uploaded_at')[0])

    def test_is_newest_checkin(self):
        user = auth.UserF(is_active=True)
        checkin1 = modelfactories.CheckinFactory()
        article = checkin1.article

        self.assertTrue(checkin1.is_newest_checkin)
        checkin2 = modelfactories.CheckinFactory(accepted_by=user,
                                                 accepted_at=datetime.datetime.now(),
                                                 status='accepted',
                                                 article=article,
                                                 uploaded_at=datetime.datetime.now())

        self.assertTrue(checkin2.is_newest_checkin)
        self.assertFalse(checkin1.is_newest_checkin)

    def test_new_checkin_has_correct_expiration_date_and_is_not_expirable(self):
        checkin = modelfactories.CheckinFactory()

        now = datetime.datetime.now()
        days_delta = datetime.timedelta(days=settings.CHECKIN_EXPIRATION_TIME_SPAN)
        next_week_date = now + days_delta

        self.assertEqual(checkin.expiration_at.date(), next_week_date.date())
        self.assertFalse(checkin.is_expirable)

    def test_if_expiration_date_is_today_then_checkin_is_expirable(self):
        now = datetime.datetime.now()

        checkin = modelfactories.CheckinFactory(expiration_at=now)

        self.assertEqual(checkin.expiration_at.date(), now.date())
        self.assertTrue(checkin.is_expirable)

    def test_validate_sequence_function(self):
        sequences = (
            (True, ["SERV_BEGIN", "SERV_END", "SERV_BEGIN", "SERV_END"]),
            (True, ["SERV_BEGIN", "SERV_BEGIN", "SERV_END", "SERV_END"]),
            (False, ["SERV_BEGIN", "SERV_BEGIN", "SERV_END", "ANOTHER_SYMBOL"]),
            (False, ["SERV_BEGIN", "SERV_BEGIN", "SERV_END"]),
            (False, ["SERV_BEGIN", "SERV_END", "SERV_END"]),
            (False, ["SERV_BEGIN", "SERV_BEGIN", "SERV_BEGIN", "SERV_BEGIN", ]),
            (False, ["SERV_END", "SERV_END", "SERV_END", "SERV_END", ]),
        )
        for expected_result, sequence in sequences:
            validation_result = misc.validate_sequence(sequence)
            self.assertEqual(expected_result, validation_result)


class ArticleTests(TestCase):

    def test_is_accepted_method_with_accepted_checkins(self):

        user = auth.UserF(is_active=True)

        article = modelfactories.ArticleFactory()
        modelfactories.CheckinFactory(accepted_by=user,
                                      accepted_at=datetime.datetime.now(),
                                      status='accepted',
                                      article=article)

        self.assertTrue(article.is_accepted())

    def test_is_accepted_method_without_accepted_checkins(self):
        article = modelfactories.ArticleFactory()

        modelfactories.CheckinFactory(article=article)
        modelfactories.CheckinFactory(article=article)

        self.assertFalse(article.is_accepted())


class CheckinWorkflowLogTests(TestCase):
    """
    Every change of Checkin's status will generate a record with info about the current status of the checkin
    This way is possible to audit the actions made with the related checkin
    """

    def setUp(self):
        self.user = auth.UserF(is_active=True)
        # Producer definition:
        group_producer = auth.GroupF(name='producer')
        self.user.groups.add(group_producer)
        self.user.save()
        # QAL 1 definitions
        self.user_qal_1 = auth.UserF(is_active=True)
        group_qal_1 = auth.GroupF(name='QAL1')
        self.user_qal_1.groups.add(group_qal_1)
        self.user_qal_1.save()
        # QAL 2 definitions
        self.user_qal_2 = auth.UserF(is_active=True)
        self.group_qal_2 = auth.GroupF(name='QAL2')
        self.user_qal_2.groups.add(self.group_qal_2)
        self.user_qal_2.save()

    def test_checkinworkflowlog_ordering(self):
        ordering = models.CheckinWorkflowLog._meta.ordering
        self.assertEqual(ordering, ['created_at'])

    def test_new_checkin_no_log(self):
        """
        generate a new checkin, must not generate any log
        """
        checkin = modelfactories.CheckinFactory()
        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin)
        self.assertEqual(logs.count(), 0)

    def test_checkin_send_to_review_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_SENT_TO_REVIEW)

    def test_checkin_do_review_level1_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_1)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_1)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_REVIEWED_QAL1)

    def test_checkin_do_review_level2_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_2)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_2)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_REVIEWED_QAL2)

    def test_checkin_do_accept_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)
        self.assertEqual("accepted", checkin.status)
        self.assertTrue(checkin.is_accepted)
        self.assertEqual(self.user_qal_2, checkin.accepted_by)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_2)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_2)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_ACCEPTED)

    def test_checkin_do_schedule_to_checkout(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)

        # do schedule to checkout
        self.assertEqual("accepted", checkin.status)
        self.assertTrue(checkin.can_be_scheduled_to_checkout)
        checkin.do_schedule_to_checkout(self.user_qal_2)
        self.assertEqual("checkout_scheduled", checkin.status)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_2)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_2)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_SCHEDULE_TO_CHECKOUT)


    def test_checkin_do_confirm_checkout(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do review by QAL1
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_1(self.user_qal_1)

        # do review by QAL2
        self.assertTrue(checkin.can_be_reviewed)
        checkin.do_review_by_level_2(self.user_qal_2)

        # do accept
        self.assertTrue(checkin.can_be_accepted)
        checkin.accept(self.user_qal_2)

        # do schedule to checkout
        self.assertTrue(checkin.can_be_scheduled_to_checkout)
        checkin.do_schedule_to_checkout(self.user_qal_2)

        # do confirm checkout
        self.assertEqual("checkout_scheduled", checkin.status)
        self.assertTrue(checkin.can_confirm_checkout)
        checkin.do_confirm_checkout()
        self.assertEqual("checkout_confirmed", checkin.status)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status)

        self.assertEqual(logs.count(), 1)
        # the user responsible is None, because is a made by THE SYSTEM (a.k.a. a celery task)
        self.assertIsNone(logs[0].user)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_CHECKOUT_CONFIRMED)

    def test_checkin_do_reject_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        rejection_text = 'your checkin is bad, and you should feel bad!'  # http://www.quickmeme.com/Zoidberg-you-should-feel-bad/?upcoming

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do reject
        self.assertTrue(checkin.can_be_rejected)
        checkin.do_reject(self.user_qal_1, rejection_text)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_1)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_1)
        expected_description = "%s - Reason: %s" % (models.MSG_WORKFLOW_REJECTED, checkin.rejected_cause)
        self.assertEqual(logs[0].description, expected_description)

    def test_checkin_send_to_pending_log(self):
        checkin = modelfactories.CheckinFactory()
        create_notices('ok', checkin)

        rejection_text = 'your checkin is bad, and you should feel bad!'  # http://www.quickmeme.com/Zoidberg-you-should-feel-bad/?upcoming

        # send to review
        self.assertTrue(checkin.can_be_send_to_review)
        checkin.send_to_review(self.user)

        # do reject
        self.assertTrue(checkin.can_be_rejected)
        checkin.do_reject(self.user_qal_1, rejection_text)

        # send to pending
        self.assertTrue(checkin.can_be_send_to_pending)
        checkin.send_to_pending(self.user_qal_2)

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status, user=self.user_qal_2)

        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].user, self.user_qal_2)
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_SENT_TO_PENDING)

    def test_do_expires_generate_log_entry(self):
        checkin = modelfactories.CheckinFactory()

        # do_expires
        checkin.do_expires()

        logs = models.CheckinWorkflowLog.objects.filter(checkin=checkin, status=checkin.status)

        self.assertEqual(logs.count(), 1)
        self.assertIsNone(logs[0].user)
        self.assertEqual(logs[0].status, 'expired')
        self.assertEqual(logs[0].description, models.MSG_WORKFLOW_EXPIRED)

    # ############################### #
    # CHECKIN NOTICES AND ERROR LEVEL #
    # ############################### #

    def test_checkin_with_notices_incomplete_service_status_must_be_in_progress(self):
        """
        For one checkin, generate various notices like incomplete processing, such as only one SERV_BEGIN
        """
        checkin = modelfactories.CheckinFactory()
        modelfactories.NoticeFactory(
            checkin=checkin,
            stage=" ", message=" ", status="SERV_BEGIN",
            created_at=datetime.datetime.now())

        self.assertFalse(checkin.is_serv_status_completed)
        self.assertEqual('in progress', checkin.get_error_level)

    def test_checkin_notices_with_less_serv_status_than_SERVICE_STATUS_MAX_STAGES_is_incompleted(self):
        """
        If a checkin's notices, are less than SERVICE_STATUS_MAX_STAGES service status (SERV_END), is incomplete
        """
        checkin = modelfactories.CheckinFactory()
        serv_status_count = models.SERVICE_STATUS_MAX_STAGES - 1
        for step in xrange(0, serv_status_count):
            modelfactories.NoticeFactory(
                checkin=checkin,
                stage=" ", message=" ", status="SERV_END",
                created_at=datetime.datetime.now())

        self.assertFalse(checkin.is_serv_status_completed)
        self.assertEqual('in progress', checkin.get_error_level)

    def test_checkin_notices_with_equal_serv_status_than_SERVICE_STATUS_MAX_STAGES_is_incompleted(self):
        """
        If a checkin's notices, are equal to SERVICE_STATUS_MAX_STAGES service status (SERV_END), still incomplete
        because only have: "SERV_END" as service status.
        """
        checkin = modelfactories.CheckinFactory()
        serv_status_count = models.SERVICE_STATUS_MAX_STAGES
        for step in xrange(0, serv_status_count):
            modelfactories.NoticeFactory(
                checkin=checkin,
                stage=" ", message=" ", status="SERV_END",
                created_at=datetime.datetime.now())

        self.assertFalse(checkin.is_serv_status_completed)
        self.assertEqual('in progress', checkin.get_error_level)

    def test_checkin_notices_with_correct_pair_of_service_status_is_completed(self):
        """
        If checkin's notices, are equal to SERVICE_STATUS_MAX_STAGES service status (SERV_END), is complete
        because each service status  has a pair: "SERV_BEGIN"/"SERV_END" as service status, and checkin.error_level
        is 'ok' because has no "error"/"warning" notices
        """
        checkin = modelfactories.CheckinFactory()
        serv_status_count = models.SERVICE_STATUS_MAX_STAGES
        for step in xrange(0, serv_status_count):
            modelfactories.NoticeFactory(
                checkin=checkin,
                stage=" ", message=" ", status="SERV_BEGIN",
                created_at=datetime.datetime.now())
            modelfactories.NoticeFactory(
                checkin=checkin,
                stage=" ", message=" ", status="SERV_END",
                created_at=datetime.datetime.now())
        self.assertTrue(checkin.is_serv_status_completed)
        self.assertEqual('ok', checkin.get_error_level)
