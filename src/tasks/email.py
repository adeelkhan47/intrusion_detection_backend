import logging
from datetime import datetime, timedelta
from datetime import timezone

import math

from common.enums import EmailStatus
from helpers.call_platform import run_platform
from helpers.common import get_emails
from model import Email, Distributor
from model.stats import Stats
from model.user import User
from model.user_emails import UserEmail
from tasks.celery import DbTask, celery_app

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__file__)


@celery_app.task(bind=True, base=DbTask)
def process_new(self, *args, **kwargs):
    session = self.session
    distributors = session.query(Distributor).filter(Distributor.status == True).all()
    #bonus_accounts = ["taitim484@gmail.com", "powertaichi2@gmail.com"]
    bonus_accounts = ["realdealautom8@gmail.com","petersmith1love@gmail.com"]
    ignored_cashapp_account_usernames = ["chango"]
    bonus_amount = 1.2
    for distributor in distributors:
        accounts = [temp.account for temp in distributor.accounts if temp.account.status]
        for account in accounts:
            ignore = False
            if account.username in ignored_cashapp_account_usernames:
                ignore = True
            account_user = [temp.user for temp in account.users if temp.user.status]
            for user in account_user:
                try:
                    logging.info(f"{user.email}")
                    emails = get_emails(user.user_auth, 20)
                    for email in emails:

                        if email['email_datetime'].tzinfo:
                            email_datetime_naive = email['email_datetime'].astimezone(timezone.utc).replace(tzinfo=None)
                        else:
                            email_datetime_naive = email['email_datetime']
                        if user.created_at.tzinfo:
                            user_created_at_naive = user.created_at.astimezone(timezone.utc).replace(tzinfo=None)
                        else:
                            user_created_at_naive = user.created_at
                        # Now you can compare
                        if email_datetime_naive > user_created_at_naive:
                            subject = email["subject"]
                            sender_email = email["sender"]
                            existing_email = session.query(Email).filter_by(email_id=email["email_id"]).first()
                            reason = ""
                            user_name = ""
                            amount_store = ""
                            try:
                                if not existing_email and sender_email != user.email:
                                    status = EmailStatus.Skipped.value
                                    platform = ""
                                    if ignore or ("cash@square.com" == sender_email and "sent you" in subject.lower()):
                                        subject_ele = subject.split(" ")
                                        subject_platform = subject_ele[len(subject_ele) - 1]
                                        user_name = subject_ele[len(subject_ele) - 2]
                                        amount = "0"
                                        for each_subject_ele in subject_ele:
                                            if "$" in each_subject_ele:
                                                amount = each_subject_ele.replace("$", "")
                                                amount = math.floor(float(amount))
                                                amount_store = f"{amount}$"
                                                if user.email.lower() in bonus_accounts:
                                                    amount = int(amount) * bonus_amount
                                                    amount = math.floor(float(amount))
                                        result = False
                                        if len(user_name) > 1:
                                            result, reason, platform = run_platform(subject_platform, account, user_name,
                                                                                amount)
                                        if result:
                                            status = EmailStatus.Successful.value
                                            stats = Stats(distributor_id=distributor.id,
                                                          account_username=account.username,
                                                          user_email=user.email, platform=platform, amount=int(amount))
                                            session.add(stats)
                                            session.commit()

                                        else:
                                            status = EmailStatus.Failed.value
                                            amount_store = ""
                                            user_name = ""
                                    else:
                                        reason = "Not Related to CashApp"
                                        status = EmailStatus.Skipped.value
                                    new_email = Email(
                                        email_id=email["email_id"],
                                        subject=email["subject"],
                                        sender_email=email["sender"],
                                        sender_name=email["sender_name"],
                                        status=status,
                                        reason=reason,
                                        platform=platform,
                                        username=user_name,
                                        amount=amount_store
                                    )
                                    session.add(new_email)
                                    session.commit()
                                    user_email = UserEmail(user_id=user.id, email_id=new_email.id)
                                    session.add(user_email)
                                    session.commit()
                                    logging.error(f"{user.email} Success.")

                            except Exception as e:
                                logging.exception(e)
                                new_email = Email(
                                    email_id=email["email_id"],
                                    subject=email["subject"],
                                    sender_email=email["sender"],
                                    sender_name=email["sender_name"],
                                    status=EmailStatus.Failed.value,
                                    reason="Internal Server Error.",
                                    platform="",
                                    username=user_name,
                                    amount=amount_store
                                )
                                session.add(new_email)
                                session.commit()
                                user_email = UserEmail(user_id=user.id, email_id=new_email.id)
                                session.add(user_email)
                                session.commit()
                except Exception as e:
                    logging.exception(e)
                    logging.error(f"Account : {account.username} and Email : {user.email} Failed.")


# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)


@celery_app.task(bind=True, base=DbTask)
def process_unauthorized_accounts(self, *args, **kwargs):
    session = self.session
    users = session.query(User).filter_by(authorised=False).all()

    for user in users:
        try:
            current_time = datetime.now(user.created_at.tzinfo)
            # Calculating the difference
            time_difference = current_time - user.created_at
            # Checking if the difference is greater than 15 minutes
            if time_difference > timedelta(minutes=10):
                session.query(User).filter_by(id=user.id).first().delete()
                session.commit()
        except Exception as e:
            logging.error(f"Account -> {user.email} Failed.")


@celery_app.task(bind=True, base=DbTask)
def process_old_emails(self, *args, **kwargs):
    session = self.session
    current_time = datetime.now()

    # Subtract 5 days from the current time
    five_days_ago = current_time - timedelta(days=5)

    # Query to get emails older than 5 days directly
    emails_to_delete = session.query(Email).filter(Email.created_at < five_days_ago).all()

    # Deleting the fetched emails
    for email in emails_to_delete:
        session.delete(email)
    session.commit()
