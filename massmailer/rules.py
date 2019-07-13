import rules

rules.add_perm('massmailer.admin', rules.is_staff)
rules.add_perm('massmailer.send', rules.is_superuser)
