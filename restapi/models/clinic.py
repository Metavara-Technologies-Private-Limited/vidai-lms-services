from django.db import models


class Clinic(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(default="lmsivf@gmail.com")  # ✅ added

    def __str__(self):
        return self.name