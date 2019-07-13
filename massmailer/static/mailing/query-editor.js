ace.define('ace/mode/custom_query_hl', function (require, exports, module) {

  var oop = require("ace/lib/oop");
  var TextHighlightRules = require("ace/mode/text_highlight_rules").TextHighlightRules;

  var CustomQueryRules = function () {

    var keywords = (
      "and|or|not|is|between|alias|contain|contains|start|starts|end|ends|match|matches|does|doesn't|with|as"
    );

    var constants = (
      "true|false|null|empty"
    );

    var funcs = (
      "concatpair|min|coalesce|concat|keystransform|valuestransform|rangestartswith|upper|daytransform|yeartransform|variance|lower|rangeendswith|minutetransform|substr|stddev|greatest|datetimedatetransform|secondtransform|max|monthtransform|sum|isempty|hourtransform|unaccent|avg|slicetransform|length|indextransform|count|now|keytransform|arraylentransform|weekdaytransform|least"
    );

    var keywordMapper = this.createKeywordMapper({
      "support.function": funcs,
      "constant.language": constants,
      "keyword": keywords
    }, "identifier");

    var strPre = "(?:i)?";

    var decimalInteger = "(?:(?:[1-9]\\d*)|(?:0))";
    var hexInteger = "(?:0[xX][\\dA-Fa-f]+)";
    var integer = "(?:" + decimalInteger + "|" + hexInteger + ")";

    var exponent = "(?:[eE][+-]?\\d+)";
    var fraction = "(?:\\.\\d+)";
    var intPart = "(?:\\d+)";
    var pointFloat = "(?:(?:" + intPart + "?" + fraction + ")|(?:" + intPart + "\\.))";
    var exponentFloat = "(?:(?:" + pointFloat + "|" + intPart + ")" + exponent + ")";
    var floatNumber = "(?:" + exponentFloat + "|" + pointFloat + ")";

    var stringEscape = "\\\\(x[0-9A-Fa-f]{2}|[0-7]{3}|[\\\\abfnrtv'\"]|U[0-9A-Fa-f]{8}|u[0-9A-Fa-f]{4})";

    this.$rules = {
      start: [
        {
          token: 'comment',
          regex: '#.*$'
        },
        {
          token: "string",           // " string
          regex: strPre + '"(?=.)',
          next: "qqstring"
        },
        {
          token: "string",           // ' string
          regex: strPre + "'(?=.)",
          next: "qstring"
        },
        {
          token: "constant.numeric", // float
          regex: floatNumber
        }, {
          token: "constant.numeric", // long integer
          regex: integer + "[lL]\\b"
        }, {
          token: "constant.numeric", // integer
          regex: integer + "\\b"
        },
        {
          token: keywordMapper,
          regex: "[a-zA-Z_$][a-zA-Z0-9_$]*\\b"
        },
        {
          token: "paren.lparen",
          regex: "[\\[\\(\\{]"
        }, {
          token: "paren.rparen",
          regex: "[\\]\\)\\}]"
        }, {
          token: "text",
          regex: "\\s+"
        }
      ],
      "qqstring": [{
        token: "constant.language.escape",
        regex: stringEscape
      }, {
        token: "string",
        regex: "\\\\$",
        next: "qqstring"
      }, {
        token: "string",
        regex: '"|$',
        next: "start"
      }, {
        defaultToken: "string"
      }],
      "qstring": [{
        token: "constant.language.escape",
        regex: stringEscape
      }, {
        token: "string",
        regex: "\\\\$",
        next: "qstring"
      }, {
        token: "string",
        regex: "'|$",
        next: "start"
      }, {
        defaultToken: "string"
      }]
    };
  };

  oop.inherits(CustomQueryRules, TextHighlightRules);
  exports.CustomQueryRules = CustomQueryRules;
});

ace.define('ace/mode/custom_query', function (require, exports, module) {

  var oop = require("ace/lib/oop");
  var TextMode = require("ace/mode/text").Mode;
  var CustomQueryRules = require("ace/mode/custom_query_hl").CustomQueryRules;

  var Mode = function () {
    this.HighlightRules = CustomQueryRules;
  };
  oop.inherits(Mode, TextMode);

  (function () {
    this.$id = "ace/mode/custom_query";
  }).call(Mode.prototype);

  exports.Mode = Mode;
});

$(function () {

  $("#id_useful_with").select2();

  $.fn.aceEditor = function (options) {
    var settings = $.extend({
      showLineNumbers: false,
      highlightActiveLine: true,
      showPrintMargin: false,
      showFoldWidgets: false,
    }, options);

    var $this = $(this);
    var $editor = $('<div/>').attr('id', $this.attr('id') + '-editor');
    $this.after($editor);
    var editor = ace.edit($editor.attr('id'));
    editor.setOptions(settings);
    editor.getSession().setMode("ace/mode/custom_query");
    editor.getSession().getDocument().setValue($this.hide().val());
    editor.getSession().on('change', function () {
      $this.val(editor.getSession().getDocument().getValue());
    });
    return editor;
  };

  var $query = $("#id_query");
  var $result_stats = $('#result-stats').hide();
  var $result_wrap = $('#result-wrap');
  var $result_error = $('#result-error');
  var $result_data = $('#result-data');
  var $result_model = $('.result-model');
  var $result_model_name = $('#result-model-name');
  var $result_aliases = $('#result-aliases');
  var $result_count = $('#result-count');
  var $result_user_count = $('#result-user-count');
  var $result_sql_query = $('#result-sql');
  var $result_pager = $('#result-pager');
  var $result_page = $('#result-page');
  var $page_previous = $('#btn-page-previous');
  var $page_next = $('#btn-page-next');
  var $page_buttons = $('#btn-page-previous, #btn-page-next');

  var editor = $query.aceEditor({
    minLines: 5,
    maxLines: 20,
    tabSize: 2,
    useSoftTabs: true
  });

  var page = 1, count = 0;

  function preview() {
    var query = editor.getSession().getDocument().getValue();
    $page_buttons.prop('disabled', true);
    $.post(PREVIEW_URL, {query: query, page: page - 1})
      .done(function (data) {
        var invalid = !!data.error;
        $result_stats.toggle(!data.error);
        $result_error.toggle(invalid);
        $result_pager.toggle(!invalid);
        $result_data.toggle(!invalid);
        $page_buttons.prop('disabled', invalid);
        $result_wrap
          .toggleClass('panel-default', !invalid)
          .toggleClass('panel-danger', invalid);
        if(data.error) {
          var e = '–';
          $result_sql_query.text(e);
          $result_error.text(data.error);
        } else {
          count = data.count;
          page = Math.max(1, Math.min(count, page));
          $page_previous.prop('disabled', page <= 1);
          $page_next.prop('disabled', page >= count);
          $result_pager.toggle(count > 0)
          $result_page.val(page);
          $result_model.text(data.model);
          $result_model_name.text(data.model_name);
          $result_aliases.empty().append(data.aliases.map(function(a) { return $('<li/>').append($('<code/>').text(a[0] + ' → ' + a[1])); }));
          $result_count.text(data.count);
          $result_user_count.text(data.user_count);
          $result_sql_query.text(data.query);
          $result_data.empty();
          if (!data.result) return;
          for (let name in data.result) {
            let r = data.result[name];
            $result_data.append($('<tr>').append($('<th>').text(name)).append($('<th>').text(r.pk)));
            for (let field in r.fields) {
              let value = r.fields[field];
              let row = $('<tr>');
              row.append($('<td>').append($('<tt>').text(field)));
              row.append($('<td>').append($('<tt>').text(value)));
              $result_data.append(row);
            }
          }
        }
      });
  }

  editor.getSession().getDocument().on('change', debounce(preview, 500));

  $page_previous.click(function (e) {
    e.preventDefault();
    if (page <= 0)
      return;
    page--;
    preview();
  });
  $page_next.click(function (e) {
    e.preventDefault();
    if (page > count)
      return;
    page++;
    preview();
  });
  $result_page
  .on('change', function () {
    var want = $result_page.val();
    page = Math.min(count, Math.max(1, want));
    $result_page.val(want);
    preview();
  })
  .on('keydown', function (e) {
    // return submits the non existent form -_-
    if (e.keyCode === 13) e.preventDefault();
  });


  // model name insert
  $('.ins-model').click(function (e) {
    e.preventDefault();
    var $this = $(this);
    var lines = editor.getSession().getDocument().getValue().split('\n');
    // comment lines
    lines = lines.map(function (l) {
      return l.match(/^\s*$|\s*#/) ? l : ("# " + l);
    });
    lines.push($this.attr('data-clsname'));
    lines.push('');
    var alias = $this.attr('data-alias');
    if (alias) {
      lines.push('alias user = .' + alias);
      lines.push('');
    }
    editor.getSession().getDocument().setValue(lines.join('\n'));
    editor.focus();
  });

  // enum insert
  $('.ins-enum ul > li > a').click(function (e) {
    e.preventDefault();
    var $this = $(this);
    var name = $this.closest('div').find('button').text().trim();
    var member = $this.text().trim();
    editor.insert(name + '.' + member);
    editor.focus();
  });

  // function insert
  $('.ins-func').click(function (e) {
    var name = $(this).text();
    editor.insert(name + '()');
    var pos = editor.getCursorPosition();
    pos.column -= 1;
    editor.moveCursorToPosition(pos);
    editor.focus();
  });

  preview();

});
