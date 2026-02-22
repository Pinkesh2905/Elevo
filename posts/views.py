from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.models import UserProfile
from .forms import CommentForm, PostForm, RepostForm
from .models import Comment, Follow, Like, Post, Repost, Share


def _build_activity_feed(posts, reposts):
    items = []

    for post in posts:
        items.append({
            "type": "post",
            "post": post,
            "actor": post.author,
            "timestamp": post.created_at,
        })

    for repost in reposts:
        items.append({
            "type": "repost",
            "post": repost.original_post,
            "repost": repost,
            "actor": repost.user,
            "timestamp": repost.created_at,
        })

    items.sort(key=lambda row: row["timestamp"], reverse=True)
    return items


@login_required
def feed_view(request):
    if request.method == "POST":
        post_form = PostForm(request.POST, request.FILES)
        if post_form.is_valid():
            post = post_form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Post shared successfully.")
            return redirect("posts:feed")
        messages.error(request, "Could not publish post. Please review the content.")
    else:
        post_form = PostForm()

    following_ids = list(
        Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
    )
    visible_user_ids = following_ids + [request.user.id]
    discover_mode = not following_ids

    base_posts = Post.objects.select_related(
        "author", "author__profile"
    ).prefetch_related(
        Prefetch("comments", queryset=Comment.objects.select_related("author", "author__profile")),
        "likes",
        "reposts",
        "shares",
    )

    base_reposts = Repost.objects.select_related(
        "user", "user__profile", "original_post", "original_post__author", "original_post__author__profile"
    ).prefetch_related(
        "original_post__likes",
        "original_post__comments",
        "original_post__reposts",
        "original_post__shares",
    )

    if discover_mode:
        posts = base_posts.all()
        reposts = base_reposts.all()
    else:
        posts = base_posts.filter(author_id__in=visible_user_ids)
        reposts = base_reposts.filter(user_id__in=visible_user_ids)

    activity_items = _build_activity_feed(posts, reposts)
    liked_post_ids = set(
        Like.objects.filter(user=request.user).values_list("post_id", flat=True)
    )

    suggested_users = User.objects.exclude(id=request.user.id).exclude(
        id__in=following_ids
    ).select_related("profile").annotate(
        posts_count=Count("posts"),
        followers_count=Count("follower_links", distinct=True),
    ).order_by("-posts_count", "-followers_count")[:6]

    context = {
        "post_form": post_form,
        "comment_form": CommentForm(),
        "repost_form": RepostForm(),
        "activity_items": activity_items,
        "liked_post_ids": liked_post_ids,
        "following_count": len(following_ids),
        "discover_mode": discover_mode,
        "suggested_users": suggested_users,
    }
    return render(request, "posts/feed.html", context)


@login_required
@require_POST
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    liked = created
    if not created:
        like.delete()
        liked = False

    return JsonResponse({
        "success": True,
        "liked": liked,
        "like_count": post.likes.count(),
    })


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    parent_comment = None
    parent_id = request.POST.get("parent_id")

    if parent_id:
        parent_comment = get_object_or_404(Comment, id=parent_id, post=post)

    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.parent = parent_comment
        comment.save()
        messages.success(request, "Comment posted.")
    else:
        messages.error(request, "Comment could not be posted.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("posts:feed")
    return redirect(next_url)


@login_required
@require_POST
def repost(request, post_id):
    original_post = get_object_or_404(Post, id=post_id)
    if original_post.author_id == request.user.id:
        messages.warning(request, "You cannot repost your own post.")
        return redirect(request.META.get("HTTP_REFERER", reverse("posts:feed")))

    form = RepostForm(request.POST)
    repost_comment = ""
    if form.is_valid():
        repost_comment = form.cleaned_data.get("comment", "").strip()

    repost_obj, created = Repost.objects.get_or_create(
        original_post=original_post,
        user=request.user,
        defaults={"comment": repost_comment},
    )

    if created:
        messages.success(request, "Reposted to your timeline.")
    else:
        if repost_comment and repost_obj.comment != repost_comment:
            repost_obj.comment = repost_comment
            repost_obj.save(update_fields=["comment"])
            messages.success(request, "Repost note updated.")
        else:
            messages.info(request, "You already reposted this.")

    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER", reverse("posts:feed")))


@login_required
@require_POST
def share_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    Share.objects.get_or_create(post=post, user=request.user)
    detail_url = request.build_absolute_uri(reverse("posts:post_detail", args=[post.id]))
    return JsonResponse({
        "success": True,
        "share_count": post.shares.count(),
        "share_url": detail_url,
    })


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(User, username=username)
    if target.id == request.user.id:
        return JsonResponse({"success": False, "message": "Cannot follow yourself."}, status=400)

    relation, created = Follow.objects.get_or_create(follower=request.user, following=target)
    following = created
    if not created:
        relation.delete()
        following = False

    followers_count = Follow.objects.filter(following=target).count()
    return JsonResponse({
        "success": True,
        "following": following,
        "followers_count": followers_count,
    })


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated successfully.")
            return redirect("posts:post_detail", post_id=post.id)
        messages.error(request, "Error updating post.")
    else:
        form = PostForm(instance=post)

    return render(request, "posts/edit_post.html", {"form": form, "post": post})


@login_required
@require_POST
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    messages.success(request, "Post deleted.")
    return redirect("posts:feed")


@login_required
def view_post_modal(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("author", "author__profile").prefetch_related(
            Prefetch("comments", queryset=Comment.objects.select_related("author", "author__profile")),
            "likes",
            "shares",
        ),
        id=post_id,
    )

    comments = post.comments.filter(parent__isnull=True).order_by("created_at")
    return render(
        request,
        "posts/post_modal.html",
        {
            "post": post,
            "comments": comments,
            "is_liked": post.is_liked_by(request.user),
        },
    )


@login_required
def post_detail(request, post_id):
    post = get_object_or_404(
        Post.objects.select_related("author", "author__profile").prefetch_related(
            Prefetch("comments", queryset=Comment.objects.select_related("author", "author__profile")),
            "likes",
            "reposts",
            "shares",
        ),
        id=post_id,
    )
    return render(
        request,
        "posts/post_detail.html",
        {
            "post": post,
            "comment_form": CommentForm(),
            "repost_form": RepostForm(),
            "is_liked": post.is_liked_by(request.user),
            "is_following_author": Follow.objects.filter(
                follower=request.user, following=post.author
            ).exists() if post.author_id != request.user.id else False,
        },
    )


@login_required
def user_profile(request, username):
    return redirect("users:public_profile", username=username)


@login_required
def search_results(request):
    query = request.GET.get("q", "").strip()
    posts = []
    users = []

    if query:
        posts = Post.objects.filter(
            Q(content__icontains=query)
            | Q(author__username__icontains=query)
            | Q(hashtags__name__icontains=query)
        ).distinct().select_related(
            "author", "author__profile"
        ).prefetch_related("likes", "comments", "shares")

        users = UserProfile.objects.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(bio__icontains=query)
        ).select_related("user")

    return render(
        request,
        "core/search_results.html",
        {"query": query, "posts": posts, "users": users},
    )
