"""
Unit tests for the profiles app (extra work beyond the course).
Run with:  python manage.py test
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class ProfileSignalTests(TestCase):
    def test_profile_created_for_new_user(self):
        user = User.objects.create_user(username='newuser', password='pass12345')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_default_avatar(self):
        user = User.objects.create_user(username='newuser', password='pass12345')
        self.assertEqual(user.profile.avatar.name, 'avatar.png')


class MyProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chris', password='pass12345')

    def test_redirects_when_logged_out(self):
        response = self.client.get(reverse('profiles:my-profile'))
        self.assertEqual(response.status_code, 302)

    def test_page_loads_when_logged_in(self):
        self.client.login(username='chris', password='pass12345')
        response = self.client.get(reverse('profiles:my-profile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chris')

    def test_update_bio_with_ajax(self):
        self.client.login(username='chris', password='pass12345')
        response = self.client.post(
            reverse('profiles:my-profile'), {'bio': 'hello from tests'}, **AJAX
        )
        self.assertEqual(response.json()['bio'], 'hello from tests')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.bio, 'hello from tests')


class NavbarLogoutTests(TestCase):
    """Beyond the course: navbar shows the logged-in user and a working Logout button."""

    def setUp(self):
        self.user = User.objects.create_user(username='chris', password='pass12345')
        self.client.login(username='chris', password='pass12345')

    def test_navbar_shows_username_and_logout(self):
        response = self.client.get(reverse('posts:main-board'))
        self.assertContains(response, 'Logged in as <b>chris</b>', html=False)
        self.assertContains(response, 'id="logout-form"')

    def test_logout_logs_user_out(self):
        logout = self.client.post(reverse('logout'))
        self.assertEqual(logout.url, '/admin/login/')
        response = self.client.get(reverse('posts:main-board'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response.url)
