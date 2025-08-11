---
layout: default
title: AI Blog
permalink: /blog/
---

<div class="container">
  <section class="hero" style="padding: 4rem 0 2rem;">
    <div class="section-header">
      <h1>AI Insights & Articles</h1>
      <p>Explore our comprehensive collection of artificial intelligence articles, research insights, and practical guides.</p>
    </div>
  </section>

  <!-- Search and Filter Section -->
  <section class="search-section" style="margin-bottom: 2rem;">
    <div class="container">
      <div class="search-box">
        <input type="search" id="search-input" placeholder="Search AI articles..." class="search-input">
        <select id="category-filter" class="category-filter">
          <option value="">All Categories</option>
          <option value="machine-learning">Machine Learning</option>
          <option value="deep-learning">Deep Learning</option>
          <option value="ai-applications">AI Applications</option>
          <option value="ai-research">AI Research</option>
          <option value="ai-ethics">AI Ethics</option>
          <option value="ai-tools">AI Tools</option>
          <option value="data-science">Data Science</option>
          <option value="computer-vision">Computer Vision</option>
        </select>
      </div>
    </div>
  </section>

  <!-- Blog Posts Grid -->
  <section class="blog-posts">
    <div class="container">
      {% if site.posts.size > 0 %}
        <div class="post-list" id="posts-container">
          {% for post in site.posts %}
          <article class="post-card" data-category="{{ post.category | default: 'general' }}">
            {% if post.image %}
            <img src="{{ post.image | relative_url }}" alt="{{ post.title }}">
            {% endif %}
            <div class="post-card-content">
              <h3>{{ post.title }}</h3>
              <p class="meta">{{ post.date | date: "%B %d, %Y" }}</p>
              {% if post.category %}
              <span class="category-tag">{{ post.category }}</span>
              {% endif %}
              <p>{{ post.description | default: post.excerpt | strip_html | truncate: 120 }}</p>
              <a href="{{ post.url | relative_url }}" class="btn btn-outline">Read More</a>
            </div>
          </article>
          {% endfor %}
        </div>
        
        <!-- No Results Message -->
        <div id="no-results" class="no-results" style="display: none; text-align: center; padding: 2rem;">
          <h3>No articles found</h3>
          <p>Try adjusting your search terms or category filter.</p>
        </div>
      {% else %}
        <div class="no-posts" style="text-align: center; padding: 2rem;">
          <h3>No articles yet</h3>
          <p>We're working on creating amazing AI content for you. Check back soon!</p>
        </div>
      {% endif %}
    </div>
  </section>

  <!-- Newsletter Signup -->
  <section class="newsletter" style="margin: 4rem 0; background: var(--gray-50); padding: 3rem 0; border-radius: var(--radius-lg);">
    <div class="container">
      <div class="section-header">
        <h2>Stay Updated with AI Insights</h2>
        <p>Get the latest AI research, breakthroughs, and insights delivered to your inbox.</p>
      </div>
      <div style="max-width: 500px; margin: 0 auto; text-align: center;">
        <div class="newsletter-form">
          <input type="email" placeholder="Enter your email address" class="newsletter-input">
          <button class="btn btn-primary">Subscribe</button>
        </div>
        <p style="font-size: 0.875rem; color: var(--gray-500); margin-top: 1rem;">
          No spam, unsubscribe at any time. We respect your privacy.
        </p>
      </div>
    </div>
  </section>
</div>

<style>
.search-section {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.search-box {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.search-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-md);
  font-size: 1rem;
  transition: var(--transition);
}

.search-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
}

.category-filter {
  padding: 0.75rem 1rem;
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-md);
  font-size: 1rem;
  background: var(--white);
  cursor: pointer;
}

.category-tag {
  display: inline-block;
  background: var(--primary);
  color: var(--white);
  padding: 0.25rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  margin-bottom: 1rem;
}

.newsletter-form {
  display: flex;
  gap: 0.5rem;
  margin-top: 1.5rem;
}

.newsletter-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 1px solid var(--gray-300);
  border-radius: var(--radius-md);
  font-size: 1rem;
}

.newsletter-input:focus {
  outline: none;
  border-color: var(--primary);
}

@media (max-width: 768px) {
  .search-box {
    flex-direction: column;
  }
  
  .newsletter-form {
    flex-direction: column;
  }
}
</style>

<script>
// Simple search and filter functionality
document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('search-input');
  const categoryFilter = document.getElementById('category-filter');
  const postsContainer = document.getElementById('posts-container');
  const noResults = document.getElementById('no-results');
  const posts = document.querySelectorAll('.post-card');

  function filterPosts() {
    const searchTerm = searchInput.value.toLowerCase();
    const selectedCategory = categoryFilter.value.toLowerCase();
    let visiblePosts = 0;

    posts.forEach(post => {
      const title = post.querySelector('h3').textContent.toLowerCase();
      const content = post.querySelector('p').textContent.toLowerCase();
      const category = post.dataset.category.toLowerCase();
      
      const matchesSearch = title.includes(searchTerm) || content.includes(searchTerm);
      const matchesCategory = !selectedCategory || category === selectedCategory;
      
      if (matchesSearch && matchesCategory) {
        post.style.display = 'block';
        visiblePosts++;
      } else {
        post.style.display = 'none';
      }
    });

    // Show/hide no results message
    if (visiblePosts === 0) {
      noResults.style.display = 'block';
      postsContainer.style.display = 'none';
    } else {
      noResults.style.display = 'none';
      postsContainer.style.display = 'grid';
    }
  }

  // Add event listeners
  searchInput.addEventListener('input', filterPosts);
  categoryFilter.addEventListener('change', filterPosts);
});
</script>
