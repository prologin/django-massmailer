import rules

rules.add_perm('mailing.admin', rules.is_staff)
rules.add_perm('mailing.send', rules.is_superuser)
