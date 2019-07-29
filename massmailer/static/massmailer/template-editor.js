(function ($) {
  $.fn.aceEditor = function (options) {
    var settings = $.extend({
      showLineNumbers: true,
      highlightActiveLine: true,
      showPrintMargin: true,
      printMarginColumn: 72,
      showFoldWidgets: false,
    }, options);

    var $this = $(this);
    var $editor = $('<div/>').attr('id', $this.attr('id') + '-editor');
    $this.after($editor);
    var editor = ace.edit($editor.attr('id'));
    editor.setOptions(settings);
    editor.getSession().setMode("ace/mode/django");
    editor.getSession().getDocument().setValue($this.hide().val());
    editor.getSession().on('change', function () {
      $this.val(editor.getSession().getDocument().getValue());
    });
    return editor;
  };

  $(function () {
    var $language = $('#id_language');
    var $use_markdown = $('#id_use_markdown');
    var $html_enabled = $('#id_html_enabled');
    var $wrap_columns = $('#id_wrap_columns');
    var query_id, page = 0, count = 0;

    $("#id_useful_queries").select2().on('select2:select', function (e) {
      query_id = e.params.data.id;
      page = 0;
      preview();
    }).on('select2:unselect', function (e) {
      query_id = null;
      preview();
    });

    var $page_previous = $('#btn-page-previous');
    $page_previous.click(function (e) {
      e.preventDefault();
      if (page <= 0)
        return;
      page--;
      preview();
    });
    var $page_next = $('#btn-page-next');
    $page_next.click(function (e) {
      e.preventDefault();
      if (page > count)
        return;
      page++;
      preview();
    });
    var $page_buttons = $('#btn-page-previous, #btn-page-next');

    var $result_count = $('#result-count');
    var $result_page = $('#result-page');
    $result_page
      .on('change', function () {
        var want = $result_page.val();
        page = Math.min(count, Math.max(1, want)) - 1;
        $result_page.val(want);
        preview();
      })
      .on('keydown', function (e) {
        // return submits the non existent form -_-
        if (e.keyCode === 13) e.preventDefault();
      });

    function preview() {
      $page_buttons.prop('disabled', query_id == null);
      $result_page.parent().hide();
      $result_count.val('');
      if (query_id == null)
        return;
      $page_buttons.prop('disabled', true);
      $.post(PREVIEW_URL, {
        html_enabled: $html_enabled.prop('checked'),
        use_markdown: $use_markdown.prop('checked'),
        wrap_columns: $wrap_columns.val(),
        query: query_id,
        page: page,
        language: $language.val(),
        subject: subject_editor.getSession().getDocument().getValue(),
        plain: plain_editor.getSession().getDocument().getValue(),
        html: html_editor.getSession().getDocument().getValue(),
      })
        .then(function (data) {
          if (data.error) {
            $('#preview-error').text(data.error);
            return;
          }
          count = data.query.count;
          page = data.query.page;
          $result_count.text(count);
          $result_page.parent().toggle(!!count);
          $page_previous.prop('disabled', page <= 0);
          $page_next.prop('disabled', page >= count - 1);
          if (!count) {
            return;
          }
          $result_page.val(page + 1).attr('max', count);
          $('#preview-subject-error').text(data.render.subject.error ? data.render.subject.error.msg : '');
          $('#preview-plain .preview-subject > div:last-child, #preview-html .preview-subject').text(data.render.subject.content);
          $('#preview-plain .preview-content > div:last-child').text(data.render.plain.content);
          $('#preview-plain-error').text(data.render.plain.error ? data.render.plain.error.msg : '');
          if ($html_enabled.prop('checked')) {
            $('#preview-html-error').text(data.render.html.error ? data.render.html.error.msg : '');
            $('#preview-html .preview-content').html(data.render.html.content);
            if ($use_markdown.prop('checked')) {
              html_editor.getSession().getDocument().setValue(data.html_template);
            }
          }
        });
    }

    function updateHtmlEnable() {
      var enable = $html_enabled.prop('checked');
      $use_markdown.parent().toggle(enable);
      $('a[href="#preview-html"]').parent().toggle(enable);
      if (!enable) {
        $('a[href="#preview-plain"]').tab('show');
      }
      $(html_editor.container).closest('.form-group').toggle(enable);
      html_editor.resize();
      html_editor.renderer.updateFull();
      if (enable)
        html_editor.setReadOnly($use_markdown.prop('checked'));
      preview();
    }

    var subject_editor = $('#id_subject').aceEditor({
      minLines: 2,
      maxLines: 10,
    });

    subject_editor.getSession().on('change', debounce(preview, 500));
    subject_editor.renderer.setScrollMargin(4, 4);

    var plain_editor = $('#id_plain_body').aceEditor({
      minLines: 10,
      maxLines: 30,
    });
    plain_editor.getSession().on('change', debounce(preview, 500));
    plain_editor.renderer.setScrollMargin(4, 4);

    var html_editor = $('#id_html_body').aceEditor({
      minLines: 10,
      maxLines: 30,
    });
    html_editor.getSession().on('change', function () {
      if (!$use_markdown.prop('checked'))
        debounce(preview, 1000);
    });
    $wrap_columns.on('change', debounce(preview, 500));
    html_editor.renderer.setScrollMargin(4, 4);

    $language.on('change', debounce(preview, 500));

    $html_enabled.on('change', updateHtmlEnable);
    $use_markdown.on('change', updateHtmlEnable);
    updateHtmlEnable();
    preview();
  });

}(jQuery));
