def filter_by_clinic(queryset, user):

    # 🔥 DEMO MODE → allow all data if no user
    if not user or not hasattr(user, "profile"):
        return queryset

    role = user.profile.role

    # Super Admin → full access
    if role and role.name and role.name.lower().strip() == "super admin":
        return queryset

    # No clinic → block
    if not user.profile.clinic:
        return queryset.none()

    # Generic handling
    if hasattr(queryset.model, "clinic"):
        return queryset.filter(clinic=user.profile.clinic)

    return queryset.filter(profile__clinic=user.profile.clinic)