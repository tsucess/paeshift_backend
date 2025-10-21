
from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class integrations(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    integration = models.CharField(default="", max_length=20)

from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class integrations(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    integration = models.CharField(default="", max_length=20)

    
