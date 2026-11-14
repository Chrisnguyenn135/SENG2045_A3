"""
Unit tests for the posts app (extra work beyond the course).
Run with:  python manage.py test
"""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from profiles.models import Profile
from .models import Post, Photo

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

# 1x1 transparent GIF saved as .png is enough for an ImageField upload test
TINY_IMAGE = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
    b'\x00\x02\x02D\x01\x00;'
)


class PostTestBase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author', password='pass12345')
        self.other = User.objects.create_user(username='other', password='pass12345')
        self.post = Post.objects.create(
            title='first post',
            body='hello',
            author=Profile.objects.get(user=self.author),
        )


class PostModelTests(PostTestBase):
    def test_str_returns_title(self):
        self.assertEqual(str(self.post), 'first post')

    def test_like_count(self):
        self.assertEqual(self.post.like_count, 0)
        self.post.liked.add(self.author, self.other)
        self.assertEqual(self.post.like_count, 2)

    def test_newest_post_comes_first(self):
        newer = Post.objects.create(
            title='second post', body='x', author=Profile.objects.get(user=self.author)
        )
        # make the first post clearly older (on Windows two posts created in the
        # same moment can get the same timestamp)
        Post.objects.filter(pk=self.post.pk).update(
            created=newer.created - timedelta(minutes=1)
        )
        self.assertEqual(Post.objects.first(), newer)


class LoginRequiredTests(PostTestBase):
    def test_main_board_redirects_when_logged_out(self):
        response = self.client.get(reverse('posts:main-board'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/', response.url)

    def test_main_board_loads_when_logged_in(self):
        self.client.login(username='author', password='pass12345')
        response = self.client.get(reverse('posts:main-board'))
        self.assertEqual(response.status_code, 200)


class PostAjaxViewTests(PostTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='author', password='pass12345')

    def test_create_post_with_ajax(self):
        response = self.client.post(
            reverse('posts:main-board'),
            {'title': 'ajax post', 'body': 'created with ajax'},
            **AJAX,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'ajax post')
        self.assertTrue(Post.objects.filter(title='ajax post').exists())

    def test_load_posts_data(self):
        response = self.client.get(reverse('posts:posts-data', args=[3]), **AJAX)
        data = response.json()
        self.assertEqual(data['size'], 1)
        self.assertEqual(data['data'][0]['title'], 'first post')
        self.assertEqual(data['data'][0]['author'], 'author')

    def test_like_then_unlike(self):
        url = reverse('posts:like-unlike')
        first = self.client.post(url, {'pk': self.post.pk}, **AJAX).json()
        self.assertEqual(first, {'liked': True, 'count': 1})
        second = self.client.post(url, {'pk': self.post.pk}, **AJAX).json()
        self.assertEqual(second, {'liked': False, 'count': 0})

    def test_author_can_update_post(self):
        response = self.client.post(
            reverse('posts:post-update', args=[self.post.pk]),
            {'title': 'new title', 'body': 'new body'},
            **AJAX,
        )
        self.assertEqual(response.json()['title'], 'new title')
        self.post.refresh_from_db()
        self.assertEqual(self.post.body, 'new body')

    def test_author_can_delete_post(self):
        self.client.post(reverse('posts:post-delete', args=[self.post.pk]), **AJAX)
        self.assertFalse(Post.objects.filter(pk=self.post.pk).exists())


class ActionPermissionTests(PostTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='other', password='pass12345')

    def test_other_user_cannot_update(self):
        response = self.client.post(
            reverse('posts:post-update', args=[self.post.pk]),
            {'title': 'hacked', 'body': 'hacked'},
            **AJAX,
        )
        self.assertContains(response, 'access denied')
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'first post')

    def test_other_user_cannot_delete(self):
        response = self.client.post(reverse('posts:post-delete', args=[self.post.pk]), **AJAX)
        self.assertContains(response, 'access denied')
        self.assertTrue(Post.objects.filter(pk=self.post.pk).exists())


class ImageUploadTests(PostTestBase):
    def setUp(self):
        super().setUp()
        self.media_dir = tempfile.mkdtemp()
        self.client.login(username='author', password='pass12345')

    def tearDown(self):
        shutil.rmtree(self.media_dir, ignore_errors=True)

    def test_upload_creates_photo(self):
        with override_settings(MEDIA_ROOT=self.media_dir):
            image = SimpleUploadedFile('test.gif', TINY_IMAGE, content_type='image/gif')
            response = self.client.post(
                reverse('posts:image-upload'),
                {'file': image, 'new_post_id': self.post.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Photo.objects.filter(post=self.post).count(), 1)
        self.assertEqual(self.post.get_photos().count(), 1)
